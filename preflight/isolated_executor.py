"""Offline build/test executor for reviewed Java/Python manifests.

No service, dependency, observer or inference execution is supported by v1.
All executable project content runs in containers, never on the trusted host.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import subprocess
import tempfile
import time
from uuid import uuid4

from preflight.execution_manifest import validate_manifest, image, integer
from preflight.petclinic_adapter import AdmissionError, digest, exact
from preflight.petclinic_evaluation import strict_json
from preflight.petclinic_source_intake import collect_archive, normalized_archive
from preflight.project_discovery import discover_pair

LOG_LIMIT = 2 * 1024 * 1024


class ExecutionError(RuntimeError):
    def __init__(self, message, output=''):
        super().__init__(message)
        self.output = output


def docker(args, timeout=60):
    """Ignore host Docker auth/proxy configuration as well as host environment."""
    with tempfile.TemporaryDirectory(prefix='wheel-empty-docker-config-') as configuration:
        return _docker(args, timeout, configuration)


def _docker(args, timeout, configuration):
    """Bound stdout/time and remove host credentials from the Docker CLI env."""
    process = subprocess.Popen(['docker', *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               env={'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'LANG': 'C.UTF-8', 'DOCKER_CONFIG': configuration})
    output = bytearray()
    deadline = time.monotonic() + timeout
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    try:
        while selector.get_map():
            if time.monotonic() >= deadline:
                raise ExecutionError('Docker operation timed out', output.decode('utf-8', errors='replace'))
            for key, _ in selector.select(min(0.2, max(0, deadline - time.monotonic()))):
                block = os.read(key.fileobj.fileno(), 65536)
                if not block:
                    selector.unregister(key.fileobj)
                    continue
                if len(output) + len(block) > LOG_LIMIT:
                    raise ExecutionError('Docker output limit exceeded', output.decode('utf-8', errors='replace'))
                output.extend(block)
        return {'returncode': process.wait(timeout=max(0.01, deadline - time.monotonic())),
                'output': output.decode('utf-8', errors='replace')}
    except subprocess.TimeoutExpired as error:
        raise ExecutionError('Docker operation timed out', output.decode('utf-8', errors='replace')) from error
    finally:
        selector.close()
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()


def start_container(name, timeout):
    result = docker(['start', '-a', name], timeout)
    state = json.loads(checked(['inspect', '--format', '{{json .State}}', name]))
    if state.get('Running') or state.get('Status') != 'exited':
        raise ExecutionError('Container did not exit', result['output'])
    result['returncode'] = state['ExitCode']
    if state.get('OOMKilled'):
        raise ExecutionError('Container memory limit exceeded', result['output'])
    return result


def checked(args, timeout=60):
    result = docker(args, timeout)
    if result['returncode']:
        raise ExecutionError('Docker control operation failed: ' + args[0], result['output'])
    return result['output']


def admit_policy(manifest, discovery, policy, repetitions):
    validate_manifest(manifest, discovery)
    exact(policy, {'schema', 'manifest_sha256', 'allowed_images', 'max_repetitions', 'total_timeout_seconds'})
    if policy['schema'] != 'wheel-local-execution-policy-v1' or policy['manifest_sha256'] != digest(manifest):
        raise AdmissionError('Unreviewed or changed manifest')
    if type(policy['allowed_images']) is not list or not 1 <= len(policy['allowed_images']) <= 8:
        raise AdmissionError('Bounded trusted image list required')
    for value in policy['allowed_images']:
        image(value)
    integer(policy['max_repetitions'], 1, 3)
    integer(repetitions, 1, policy['max_repetitions'])
    integer(policy['total_timeout_seconds'], 10, 1800)
    if manifest['dependencies'] or manifest['observers'] or any(p['service'] is not None for p in manifest['projects']):
        raise AdmissionError('v1 supports offline build/test projects only; services/dependencies/observers unsupported')
    if any(p['image'] not in policy['allowed_images'] for p in manifest['projects']):
        raise AdmissionError('Image outside trusted execution policy')


def container_flags(manifest, name, volume, archive=None, network="none", readonly_work=False):
    limits = manifest['limits']
    flags = ['--name', name, '--pull', 'never', '--network', network, '--read-only', '--user', '1000:1000',
             '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--cpus', str(limits['cpu_millis'] / 1000),
             '--memory', str(limits['memory_mb']) + 'm', '--memory-swap', str(limits['memory_mb']) + 'm',
             '--pids-limit', str(limits['pids']), '--tmpfs', '/tmp:rw,uid=1000,gid=1000,size=256m',
             '--env', 'HOME=/tmp', '--mount', 'type=volume,src=' + volume + ',dst=/work' + (',readonly' if readonly_work else '')]
    if archive is not None:
        flags += ['--mount', 'type=bind,src=' + str(archive) + ',dst=/input/source.tar.gz,readonly']
    return flags


def inspect_container(name, volume, archive=None, network="none", readonly_work=False):
    record = json.loads(checked(['inspect', name]))[0]
    host, config = record['HostConfig'], record['Config']
    binds = host.get('Binds')
    mounts = host.get('Mounts', [])
    expected = [{'Type': 'volume', 'Source': volume, 'Target': '/work', 'ReadOnly': readonly_work}]
    if archive is not None:
        expected.append({'Type': 'bind', 'Source': str(archive), 'Target': '/input/source.tar.gz', 'ReadOnly': True})
    normalized = lambda values: sorted((v['Type'], v['Source'], v['Target'], v.get('ReadOnly', False)) for v in values)
    if (host['NetworkMode'] != network or not host['ReadonlyRootfs'] or host['Privileged']
            or config['User'] != '1000:1000' or binds or normalized(mounts) != normalized(expected)
            or host.get('CapAdd') or host.get('CapDrop') != ['ALL']
            or not any('no-new-privileges' in value for value in host.get('SecurityOpt', []))):
        raise ExecutionError('Container isolation differs from reviewed policy')
    return {'network': host['NetworkMode'], 'read_only_root': host['ReadonlyRootfs'],
            'user': config['User'], 'mounts': mounts, 'cap_drop': host['CapDrop'],
            'source_archive_mount': archive is not None}


def run_pair(baseline, candidate, source, manifest, policy, output, repetitions=1):
    """Policy must be trusted independently of external source/model output."""
    exact(source, {'baseline_sha256', 'candidate_sha256', 'baseline_root', 'candidate_root'})
    discovery = discover_pair(baseline, candidate, source['baseline_sha256'], source['candidate_sha256'],
                              source['baseline_root'], source['candidate_root'])
    admit_policy(manifest, discovery, policy, repetitions)  # Before Docker or source materialization.
    files = {side: collect_archive(raw, source[side + '_sha256'], source[side + '_root'])
             for side, raw in [('baseline', baseline), ('candidate', candidate)]}
    for side in files:
        for project in manifest['projects']:
            prefix = '' if project['root'] == '.' else project['root'] + '/'
            for command in project['build'] + project['test']:
                if command['argv'][0].startswith('./'):
                    raise AdmissionError('Repository wrappers are not supported by offline executor v1')
            if prefix and not any(p.startswith(prefix) for p in files[side]):
                raise AdmissionError('Project directory missing from admitted archive')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    report = {'schema': 'wheel-offline-build-test-result-v1', 'status': 'execution_error',
              'manifest_sha256': digest(manifest), 'discovery_sha256': digest(discovery),
              'policy_sha256': digest(policy), 'source': source, 'worlds': [], 'cleanup_errors': [],
              'model_requests': 0, 'business_behavior_verified': False}
    deadline = time.monotonic() + policy['total_timeout_seconds']
    world_deadline = deadline
    def remaining(maximum):
        value = min(maximum, deadline - time.monotonic(), world_deadline - time.monotonic())
        if value <= 0:
            raise ExecutionError('Total execution budget exhausted')
        return value
    try:
        with tempfile.TemporaryDirectory(prefix='wheel-external-source-') as temporary:
            archives = {}
            for side in files:
                archives[side] = Path(temporary) / (side + '.tar.gz')
                archives[side].write_bytes(normalized_archive(files[side]))
            for trial in range(1, repetitions + 1):
                for side in ('baseline', 'candidate'):
                    for project in manifest['projects']:
                        identity = 'wheel-offline-' + uuid4().hex
                        volume = identity + '-work'
                        names, volume_created = [], False
                        world = {'trial': trial, 'side': side, 'project': project['id'], 'status': 'execution_error',
                                 'source_identity_sha256': discovery[side]['source_identity_sha256'],
                                 'volume': volume, 'commands': [], 'isolation': []}
                        report['worlds'].append(world)
                        world_deadline = min(deadline, time.monotonic() + manifest['limits']['world_timeout_seconds'])
                        try:
                            checked(['volume', 'create', volume], remaining(30))
                            volume_created = True
                            # Trusted helper only changes ownership of the empty disposable volume.
                            helper = identity + '-owner'
                            names.append(helper)
                            checked(['create', '--name', helper, '--pull', 'never', '--network', 'none', '--read-only',
                                     '--cap-drop', 'ALL', '--cap-add', 'CHOWN', '--security-opt', 'no-new-privileges',
                                     '--mount', 'type=volume,src=' + volume + ',dst=/work', '--entrypoint', 'chown',
                                     project['image'], '1000:1000', '/work'], remaining(30))
                            if start_container(helper, remaining(30))['returncode']:
                                raise ExecutionError('Disposable ownership initialization failed')
                            extract = identity + '-extract'
                            names.append(extract)
                            checked(['create', *container_flags(manifest, extract, volume, archives[side]),
                                     '--entrypoint', 'tar', project['image'], '-xzf', '/input/source.tar.gz',
                                     '-C', '/work', '--strip-components=1'], remaining(30))
                            world['isolation'].append(inspect_container(extract, volume, archives[side]))
                            if start_container(extract, remaining(30))['returncode']:
                                raise ExecutionError('Admitted archive extraction failed')
                            failed = False
                            for phase in ('build', 'test'):
                                for index, command in enumerate(project[phase]):
                                    name = identity + '-' + phase + '-' + str(index)
                                    names.append(name)
                                    workdir = '/work' if project['root'] == '.' else '/work/' + project['root']
                                    checked(['create', *container_flags(manifest, name, volume), '--workdir', workdir,
                                             '--entrypoint', command['argv'][0], project['image'], *command['argv'][1:]], remaining(30))
                                    world['isolation'].append(inspect_container(name, volume))
                                    result = start_container(name, remaining(command['timeout_seconds']))
                                    log = side + '-' + str(trial) + '-' + project['id'] + '-' + phase + '-' + str(index) + '.log'
                                    (output / log).write_text(result['output'])
                                    world['commands'].append({'phase': phase, 'index': index, 'returncode': result['returncode'], 'log': log})
                                    if result['returncode']:
                                        world['status'] = phase + '_failed'
                                        failed = True
                                        break
                                if failed:
                                    break
                            if not failed:
                                world['status'] = 'build_and_tests_passed'
                        except ExecutionError as error:
                            log = side + '-' + str(trial) + '-' + project['id'] + '-error.log'
                            (output / log).write_text(error.output)
                            world.update(error=str(error), error_log=log)
                            raise
                        finally:
                            for name in reversed(names):
                                try:
                                    if docker(['rm', '-f', name], 30)['returncode']:
                                        report['cleanup_errors'].append(name)
                                except Exception:
                                    report['cleanup_errors'].append(name)
                            if volume_created:
                                try:
                                    if docker(['volume', 'rm', volume], 30)['returncode']:
                                        report['cleanup_errors'].append(volume)
                                except Exception:
                                    report['cleanup_errors'].append(volume)
                            (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
                        if report['cleanup_errors']:
                            raise ExecutionError('Disposable resource cleanup failed')
                        if side == 'baseline' and world['status'] != 'build_and_tests_passed':
                            report['status'] = 'baseline_invalid'
                            return report
            report['status'] = ('candidate_checks_failed' if any(w['status'] != 'build_and_tests_passed' for w in report['worlds'])
                                else 'build_and_tests_passed')
    except Exception as error:
        report['status'] = 'execution_error'
        report['error_type'] = type(error).__name__
        report['error'] = str(error)[:500]
    finally:
        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'candidate', 'source', 'manifest', 'policy', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--repetitions', type=int, default=1)
    args = parser.parse_args()
    def read(path, maximum):
        with path.open('rb') as stream:
            raw = stream.read(maximum + 1)
        if len(raw) > maximum:
            raise AdmissionError('Input exceeds size limit')
        return raw
    result = run_pair(read(args.baseline, 32 * 1024 * 1024), read(args.candidate, 32 * 1024 * 1024),
                      strict_json(read(args.source, 1024 * 1024).decode()),
                      strict_json(read(args.manifest, 1024 * 1024).decode()),
                      strict_json(read(args.policy, 1024 * 1024).decode()), args.output, args.repetitions)
    print(json.dumps({'status': result['status'], 'worlds': len(result['worlds']), 'business_behavior_verified': False}))
    if result['status'] != 'build_and_tests_passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
