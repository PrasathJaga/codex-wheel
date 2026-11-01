"""Stateless HTTP lifecycle on fresh internal networks; no business verdicts."""
import argparse
import hashlib
import http.client
import ipaddress
import json
import multiprocessing
from pathlib import Path
import tempfile
import time
from uuid import uuid4

from preflight.execution_manifest import validate_manifest, image, integer
from preflight.isolated_executor import checked, docker, container_flags, inspect_container, start_container, ExecutionError
from preflight.petclinic_adapter import AdmissionError, digest, exact
from preflight.petclinic_evaluation import strict_json
from preflight.petclinic_source_intake import collect_archive, normalized_archive
from preflight.project_discovery import discover_pair


def admit(manifest, discovery, policy, repetitions):
    validate_manifest(manifest, discovery)
    exact(policy, {'schema', 'manifest_sha256', 'allowed_images', 'max_repetitions', 'total_timeout_seconds'})
    if policy['schema'] != 'wheel-service-execution-policy-v1' or policy['manifest_sha256'] != digest(manifest):
        raise AdmissionError('Unreviewed or changed service manifest')
    if type(policy['allowed_images']) is not list or not 1 <= len(policy['allowed_images']) <= 8:
        raise AdmissionError('Trusted image list required')
    for value in policy['allowed_images']:
        image(value)
    integer(policy['max_repetitions'], 1, 3)
    integer(repetitions, 1, policy['max_repetitions'])
    integer(policy['total_timeout_seconds'], 10, 1800)
    if (len(manifest['projects']) != 1 or manifest['projects'][0]['service'] is None
            or manifest['dependencies'] or manifest['observers']
            or manifest['projects'][0]['service']['environment_bindings']):
        raise AdmissionError('v1 requires one stateless HTTP service; dependencies and observers unsupported')
    project = manifest['projects'][0]
    if project['image'] not in policy['allowed_images']:
        raise AdmissionError('Unreviewed runtime image')
    if any(c['argv'][0].startswith('./') for c in project['build'] + project['test'] + [project['service']['start']]):
        raise AdmissionError('Repository wrappers unsupported')


def endpoint(container, network):
    net = json.loads(checked(['network', 'inspect', network]))[0]
    service = json.loads(checked(['inspect', container]))[0]
    if not net['Internal'] or net['Name'] != network:
        raise ExecutionError('Expected internal network')
    networks = service['NetworkSettings']['Networks']
    if set(networks) != {network}:
        raise ExecutionError('Unexpected service network membership')
    address = ipaddress.ip_address(networks[network]['IPAddress'])
    subnets = [ipaddress.ip_network(c['Subnet']) for c in net['IPAM']['Config'] if c.get('Subnet')]
    if not address.is_private or address.is_loopback or not any(address in subnet for subnet in subnets):
        raise ExecutionError('Service IP is not inside its private network')
    if service['HostConfig'].get('PortBindings'):
        raise ExecutionError('Published service ports forbidden')
    return str(address)


def _raw_health_request(address, port, path, timeout):
    """No proxy, redirect following, cookies, auth or arbitrary URL transport."""
    connection = http.client.HTTPConnection(address, port, timeout=timeout)
    try:
        connection.request('GET', path, headers={'Connection': 'close'})
        response = connection.getresponse()
        body = response.read(65537)
        if len(body) > 65536:
            raise ExecutionError('Health response exceeds limit')
        return {'status': response.status, 'body_sha256': hashlib.sha256(body).hexdigest(),
                'body_preview': body[:2048].decode('utf-8', errors='replace'), 'body_bytes': len(body)}
    finally:
        connection.close()



def _health_worker(sender, address, port, path, timeout):
    try:
        sender.send({'kind': 'response', 'value': _raw_health_request(address, port, path, timeout)})
    except ExecutionError as error:
        sender.send({'kind': 'execution_error', 'reason': str(error)})
    except Exception as error:
        sender.send({'kind': 'transport_error', 'error_type': type(error).__name__})
    finally:
        sender.close()


def health_request(address, port, path, timeout):
    """Hard deadline around a trusted HTTP worker, including slow headers/body."""
    context = multiprocessing.get_context('spawn')
    receiver, sender = context.Pipe(duplex=False)
    worker = context.Process(target=_health_worker, args=(sender, address, port, path, timeout), daemon=True)
    worker.start()
    sender.close()
    try:
        if not receiver.poll(timeout):
            return {'error_type': 'HealthDeadlineExceeded'}
        try:
            result = receiver.recv()
        except EOFError:
            raise ExecutionError('Health worker exited without evidence')
        if result['kind'] == 'execution_error':
            raise ExecutionError(result['reason'])
        if result['kind'] == 'transport_error':
            return {'error_type': result['error_type']}
        return result['value']
    finally:
        receiver.close()
        if worker.is_alive():
            worker.terminate()
        worker.join(timeout=1)
        if worker.is_alive():
            worker.kill()
            worker.join(timeout=1)
        if worker.is_alive():
            raise ExecutionError('Health worker cleanup failed')

def run_service_pair(baseline, candidate, source, manifest, policy, output, repetitions=1, *, postgres=False, experiment=None):
    exact(source, {'baseline_sha256', 'candidate_sha256', 'baseline_root', 'candidate_root'})
    discovery = discover_pair(baseline, candidate, source['baseline_sha256'], source['candidate_sha256'],
                              source['baseline_root'], source['candidate_root'])
    if postgres:
        from preflight.postgres_lifecycle import admit_database, validate_seeds, PostgresWorld
        admit_database(manifest, discovery, policy, repetitions)
    else:
        admit(manifest, discovery, policy, repetitions)
    admitted = {side: collect_archive(raw, source[side + '_sha256'], source[side + '_root'])
                for side, raw in [('baseline', baseline), ('candidate', candidate)]}
    if postgres:
        validate_seeds(manifest, admitted)
    if experiment is not None:
        from preflight.http_experiment import admit_experiment
        experiment = admit_experiment(manifest, policy, admitted, experiment)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    report = {'schema': 'wheel-service-lifecycle-result-v1', 'status': 'execution_error', 'worlds': [],
              'source': source, 'manifest_sha256': digest(manifest), 'policy_sha256': digest(policy),
              'discovery_sha256': digest(discovery), 'cleanup_errors': [],
              'model_requests': 0, 'business_behavior_verified': False}
    if experiment is not None:
        report['experiment_sha256'] = digest(experiment)
        (output / 'experiment.json').write_text(json.dumps(experiment, indent=2) + '\n')
    deadline = time.monotonic() + policy['total_timeout_seconds']
    world_deadline = deadline
    def budget(limit=30):
        remaining = min(limit, deadline - time.monotonic(), world_deadline - time.monotonic())
        if remaining <= 0:
            raise ExecutionError('Service execution budget exhausted')
        return remaining
    project = manifest['projects'][0]
    runtime = project['service']
    try:
        with tempfile.TemporaryDirectory(prefix='wheel-service-source-') as temporary:
            archives = {}
            for side in admitted:
                archives[side] = Path(temporary) / (side + '.tar.gz')
                archives[side].write_bytes(normalized_archive(admitted[side]))
            for trial in range(1, repetitions + 1):
                for side in ('baseline', 'candidate'):
                    identity = 'wheel-service-' + uuid4().hex
                    volume, network, service = identity + '-work', identity + '-net', identity + '-api'
                    world = {'trial': trial, 'side': side, 'status': 'execution_error', 'commands': [],
                             'health_attempts': [], 'volume': volume, 'network': network,
                             'source_identity_sha256': discovery[side]['source_identity_sha256'], 'isolation': []}
                    report['worlds'].append(world)
                    world_deadline = min(deadline, time.monotonic() + manifest['limits']['world_timeout_seconds'])
                    names, volume_created, network_created, service_created = [], False, False, False
                    database = None
                    try:
                        checked(['volume', 'create', volume], budget())
                        volume_created = True
                        helper = identity + '-owner'
                        names.append(helper)
                        checked(['create', '--name', helper, '--pull', 'never', '--network', 'none', '--read-only',
                                 '--cap-drop', 'ALL', '--cap-add', 'CHOWN', '--security-opt', 'no-new-privileges',
                                 '--mount', 'type=volume,src=' + volume + ',dst=/work', '--entrypoint', 'chown',
                                 project['image'], '1000:1000', '/work'], budget())
                        if start_container(helper, budget())['returncode']:
                            raise ExecutionError('Volume ownership initialization failed')
                        extract = identity + '-extract'
                        names.append(extract)
                        checked(['create', *container_flags(manifest, extract, volume, archives[side]),
                                 '--entrypoint', 'tar', project['image'], '-xzf', '/input/source.tar.gz',
                                 '-C', '/work', '--strip-components=1'], budget())
                        world['isolation'].append(inspect_container(extract, volume, archives[side]))
                        if start_container(extract, budget())['returncode']:
                            raise ExecutionError('Source extraction failed')
                        workdir = '/work' if project['root'] == '.' else '/work/' + project['root']
                        checks_passed = True
                        for phase in ('build', 'test'):
                            for index, command in enumerate(project[phase]):
                                name = identity + '-' + phase + '-' + str(index)
                                names.append(name)
                                checked(['create', *container_flags(manifest, name, volume), '--workdir', workdir,
                                         '--entrypoint', command['argv'][0], project['image'], *command['argv'][1:]], budget())
                                world['isolation'].append(inspect_container(name, volume))
                                result = start_container(name, budget(command['timeout_seconds']))
                                log = side + '-' + str(trial) + '-' + phase + '-' + str(index) + '.log'
                                (output / log).write_text(result['output'])
                                world['commands'].append({'phase': phase, 'index': index, 'returncode': result['returncode'], 'log': log})
                                if result['returncode']:
                                    world['status'] = phase + '_failed'
                                    checks_passed = False
                                    break
                            if not checks_passed:
                                break
                        if checks_passed:
                            checked(['network', 'create', '--internal', network], budget())
                            network_created = True
                            environment = []
                            if postgres:
                                database = PostgresWorld(manifest, admitted[side], network, identity, budget)
                                names.append(database.name)
                                world['database'] = database.start()
                                world['snapshots'] = {'initial': database.snapshot()}
                                environment = database.bindings()
                            names.append(service)
                            checked(['create', *container_flags(manifest, service, volume, network=network, readonly_work=True), *environment,
                                     '--workdir', workdir, '--entrypoint', runtime['start']['argv'][0], project['image'],
                                     *runtime['start']['argv'][1:]], budget())
                            service_created = True
                            world['isolation'].append(inspect_container(service, volume, network=network, readonly_work=True))
                            checked(['start', service], budget())
                            network_state = json.loads(checked(['network', 'inspect', network], budget()))[0]
                            if not network_state['Internal']:
                                raise ExecutionError('Expected internal network')
                            world['internal_network_verified'] = True
                            initial_state = json.loads(checked(['inspect', '--format', '{{json .State}}', service], budget()))
                            if initial_state.get('OOMKilled'):
                                raise ExecutionError('Service memory limit exceeded')
                            if initial_state['Running']:
                                address = endpoint(service, network)
                                ready_until = min(world_deadline, deadline, time.monotonic() + runtime['health']['timeout_seconds'],
                                                  time.monotonic() + runtime['start']['timeout_seconds'])
                                world['status'] = 'health_not_ready'
                            else:
                                ready_until = time.monotonic()
                                world.update(status='service_start_failed', exit_code=initial_state['ExitCode'])
                            while time.monotonic() < ready_until:
                                state = json.loads(checked(['inspect', '--format', '{{json .State}}', service], budget()))
                                if state.get('OOMKilled'):
                                    raise ExecutionError('Service memory limit exceeded')
                                if not state['Running']:
                                    world.update(status='service_start_failed', exit_code=state['ExitCode'], oom_killed=state.get('OOMKilled', False))
                                    break
                                try:
                                    attempt = health_request(address, runtime['port'], runtime['health']['path'], max(0.01, min(2, ready_until - time.monotonic())))
                                except (OSError, http.client.HTTPException) as error:
                                    attempt = {'error_type': type(error).__name__}
                                if database and 'body_preview' in attempt:
                                    attempt['body_preview'] = database.sanitize(attempt['body_preview'])
                                world['health_attempts'].append(attempt)
                                if attempt.get('status') == runtime['health']['status']:
                                    world['status'] = 'service_ready'
                                    break
                                time.sleep(min(0.2, max(0, ready_until - time.monotonic())))
                            world['internal_network_verified'] = True
                            if database:
                                world['snapshots']['after_health'] = database.snapshot()
                            if experiment is not None and world['status'] == 'service_ready':
                                from preflight.http_experiment import execute
                                address = endpoint(service, network)
                                world['experiment'] = execute(experiment, address, runtime['port'], budget(60))
                                if world['experiment']['status'] == 'execution_error':
                                    raise ExecutionError('Bounded HTTP experiment failed: ' + world['experiment']['error'])
                            if database and experiment is not None:
                                world['snapshots']['after_experiment'] = database.snapshot()
                            checked(['stop', '--time', '5', service], budget(10))
                            stopped = json.loads(checked(['inspect', '--format', '{{json .State}}', service], budget()))
                            if stopped['Running']:
                                raise ExecutionError('Service did not stop')
                            world['stopped_before_cleanup'] = True
                            if database:
                                world['snapshots']['after_stop'] = database.snapshot()
                    except ExecutionError as error:
                        world['error'] = database.sanitize(str(error)) if database else str(error)
                        log = side + '-' + str(trial) + '-execution-error.log'
                        (output / log).write_text(database.sanitize(error.output) if database else error.output)
                        world['error_log'] = log
                        raise
                    finally:
                        if service_created:
                            try:
                                result = docker(['logs', service], 10)
                                log = side + '-' + str(trial) + '-service.log'
                                (output / log).write_text(database.sanitize(result['output']) if database else result['output'])
                                world['service_log'] = log
                            except ExecutionError as error:
                                log = side + '-' + str(trial) + '-service-partial.log'
                                (output / log).write_text(database.sanitize(error.output) if database else error.output)
                                world['service_log'] = log
                                world['status'] = 'execution_error'
                                world['error'] = database.sanitize(str(error)) if database else str(error)
                        if database:
                            try:
                                db_log = docker(['logs', database.name], 10)
                                (output / (side+'-'+str(trial)+'-database.log')).write_text(database.sanitize(db_log['output']))
                            except Exception:
                                report['cleanup_errors'].append(database.name+'-logs')
                        for name in reversed(names):
                            try:
                                if docker(['rm', '-f', name], 30)['returncode']:
                                    report['cleanup_errors'].append(name)
                            except Exception:
                                report['cleanup_errors'].append(name)
                        for kind, name, created in [('network', network, network_created), ('volume', volume, volume_created)]:
                            if created:
                                try:
                                    if docker([kind, 'rm', name], 30)['returncode']:
                                        report['cleanup_errors'].append(name)
                                except Exception:
                                    report['cleanup_errors'].append(name)
                        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
                    if report['cleanup_errors'] or world['status'] == 'execution_error':
                        raise ExecutionError('Service infrastructure or cleanup failure')
                    if side == 'baseline' and (world['status'] != 'service_ready' or
                            experiment is not None and world.get('experiment', {}).get('status') != 'contract_satisfied'):
                        report['status'] = 'baseline_invalid'
                        return report
            report['status'] = 'service_lifecycle_passed' if all(w['status'] == 'service_ready' for w in report['worlds']) else 'candidate_lifecycle_failed'
            if experiment is not None and report['status'] == 'service_lifecycle_passed':
                verdicts = [w['experiment']['status'] for w in report['worlds'] if w['side'] == 'candidate']
                report['status'] = ('no_violation_observed' if all(v == 'contract_satisfied' for v in verdicts) else
                                    ('confirmed_contract_violation' if repetitions >= 2 else 'observed_contract_violation')
                                    if all(v == 'contract_violated' for v in verdicts) else 'inconclusive')
                report['approved_http_expectations_checked'] = True
    except Exception as error:
        report.update(status='execution_error', error_type=type(error).__name__, error=str(error)[:500])
    finally:
        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'candidate', 'source', 'manifest', 'policy', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--repetitions', type=int, default=1)
    parser.add_argument('--experiment', type=Path, help='Trusted frozen interface/contract/plan/policy bundle')
    parser.add_argument('--postgres', action='store_true', help='Use reviewed disposable Postgres policy')
    args = parser.parse_args()
    def read(path, maximum):
        with path.open('rb') as stream:
            raw = stream.read(maximum + 1)
        if len(raw) > maximum:
            raise AdmissionError('Service input exceeds size limit')
        return raw
    report = run_service_pair(read(args.baseline, 32 * 1024 * 1024), read(args.candidate, 32 * 1024 * 1024),
                              strict_json(read(args.source, 1024 * 1024).decode()),
                              strict_json(read(args.manifest, 1024 * 1024).decode()),
                              strict_json(read(args.policy, 1024 * 1024).decode()), args.output, args.repetitions, postgres=args.postgres,
                              experiment=strict_json(read(args.experiment, 1024 * 1024).decode()) if args.experiment else None)
    print(json.dumps({'status': report['status'], 'worlds': len(report['worlds']), 'business_behavior_verified': False}))
    if report['status'] not in ('service_lifecycle_passed', 'no_violation_observed'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
