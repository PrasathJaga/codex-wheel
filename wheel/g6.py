"""G6: three fresh pairs per frozen Meta plan, controls, constrained containers.

Run via the dedicated Actions workflow. Does not silently fall back to host
execution, manual experiment selection or mocked inference.
"""
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import time

from wheel.experiment import ROOT, JAVA, CLIENT, DOMAIN, digest, child_env, snapshot
from wheel.investigator import Investigator, InvestigatorAbstained
from wheel.isolation import DockerRuntime, UnixBroker
from wheel.meta_agent import MetaAgent, fingerprint
from wheel.plan_guard import PlanGuard, IntegrityError
from wheel.proxy import Gateway
from wheel.repeatability import POLICY, TRIALS, make_plan, validate_pair, summarize
from wheel.verifier import check


def variants():
    java = (ROOT / DOMAIN).read_text()
    python = (ROOT / CLIENT).read_text()
    needle = 'if (prior != null) {'
    retry = 'if response.status_code==502:\n                if attempt<max_attempts:\n                    continue'
    if java.count(needle) != 1 or python.count(retry) != 1:
        raise IntegrityError('Seed mutation anchor drift')
    return ({'base': java,
             'M1': java.replace(needle, 'if (prior != null && request.amountMinorUnits() > 2500) {'),
             'B1': java.replace('var prior =', 'final var prior =')},
            {'base': python,
             'M2': python.replace(retry, 'if response.status_code==502:\n                if attempt<max_attempts:\n                    key = str(uuid.uuid4())\n                    continue'),
             'B2': python.replace('last_exception: Exception | None = None',
                                  'last_exception: Exception | None = None  # benign annotation')})


def revision():
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--'], cwd=ROOT, check=True,
                   capture_output=True)
    if os.getenv('GITHUB_SHA', sha) != sha:
        raise IntegrityError('Checkout revision does not match workflow revision')
    return sha


def source_view(case, java, python):
    return {DOMAIN: {'base': java['base'], 'candidate': java.get(case, java['base'])},
            CLIENT: {'base': python['base'], 'candidate': python.get(case, python['base'])}}


def source_hashes(view):
    return {side: {version: digest(text.encode()) for version, text in view[path].items()}
            for side, path in [('java', DOMAIN), ('python', CLIENT)]}


def build_jars(java, scratch):
    jars = {}
    # Build isolated copies rather than rewriting pinned tracked source on disk.
    for name, text in java.items():
        project = scratch / ('build-' + name)
        shutil.copytree(ROOT / JAVA, project, ignore=shutil.ignore_patterns('target', '.smoke-classes'))
        (project / DOMAIN.removeprefix(JAVA + '/')).write_text(text)
        subprocess.run(['mvn', '-B', '-f', str(project / 'pom.xml'), 'package', '-DskipTests'],
                       check=True, env=child_env(), timeout=240)
        jars[name] = project / 'target/refund-api-java-0.1.0-SNAPSHOT.jar'
    return jars


def verify_events(events, effects, rule, transport_errors):
    if not events or not effects:
        raise IntegrityError('Missing HTTP or committed-effect evidence')
    expected = 1 if rule['action'] == 'PASS_THROUGH' else 2
    if len(events) != expected or events[0]['action'] != rule['action']:
        raise IntegrityError('Locked intervention did not execute')
    if [e['action'] for e in events[1:]] != ['PASS_THROUGH'] * (expected - 1):
        raise IntegrityError('Fault applied more than once')
    if any(e['upstream_status'] != 200 or not e['commit_evidence'] for e in events):
        raise IntegrityError('Post-commit boundary not proven')
    if bool(transport_errors) != (rule['action'] == 'DROP_DOWNSTREAM_BEFORE_RESPONSE'):
        raise IntegrityError('Unexpected downstream transport behavior')
    committed_ids = {row['effect_id'] for row in effects}
    for event in events:
        proof = event['commit_evidence']
        if (event['upstream_body']['refund_effect_id'] != proof['effect_id'] or
                proof['effect_id'] not in committed_ids or proof['rows_before_downstream_action'] < 1):
            raise IntegrityError('Commit evidence does not link to final ledger')


def world(runtime, plan, trial, which, jars, java, python, out, scratch, guard, manifest):
    case = plan['case']; label = f'{plan["id"]}-{trial}-{which}'
    directory = scratch / label; directory.mkdir()
    ledger_dir = directory / 'state'; ledger_dir.mkdir()
    bridge = directory / 'bridge'; bridge.mkdir()
    ledger = ledger_dir / 'ledger.tsv'
    j = case if which == 'candidate' and case in java else 'base'
    p = case if which == 'candidate' and case in python else 'base'
    module = directory / 'client.py'; module.write_text(python[p])
    guard.bind(module, python[p].encode())
    guard.verify('before_world:' + label)
    if revision() != manifest['commit']: raise IntegrityError('Wrong-branch drift')
    record = {'label': label, 'plan_id': plan['id'], 'case': case, 'world': which,
              'trial': trial, 'status': 'analysis_error', 'plan_hash': manifest['plan_hash'],
              'fixture_sha256': fingerprint(plan['fixture']), 'seed_sha256': fingerprint(plan['seed']),
              'rule_sha256': fingerprint(plan['rule']), 'policy': POLICY,
              'images': copy.deepcopy(runtime.images), 'java_sha256': digest(java[j].encode()),
              'python_sha256': digest(module.read_bytes()), 'jar_sha256': digest(jars[j].read_bytes()),
              'reset_empty': False, 'restart_recovered': False, 'oracle_pass': None,
              'effects': [], 'events': [], 'transport_errors': [], 'started_at': datetime.now(timezone.utc).isoformat()}
    started = time.monotonic()
    token = secrets.token_hex(32)
    with (out / (label + '.log')).open('w') as log:
        name, port = runtime.start_java(jars[j], ledger_dir, token, log)
        try:
            record['reset_empty'] = snapshot(port, token) == [] and not ledger.exists()
            if not record['reset_empty']: raise IntegrityError('Ledger state leaked between worlds')
            def observe(upstream):
                rows = ledger.read_text().splitlines()
                if not any(row.split('\t')[0] == upstream['refund_effect_id'] for row in rows):
                    raise IntegrityError('Upstream success before persisted effect')
                return {'effect_id': upstream['refund_effect_id'], 'ledger_sha256': digest(ledger.read_bytes()),
                        'rows_before_downstream_action': len(rows)}
            with Gateway(port, plan['rule'], observe) as gateway:
                with UnixBroker(bridge / 'gateway.sock', gateway.port):
                    guard.verify('before_wrapper:' + label)
                    outcome = runtime.wrapper(module, bridge, plan['seed']['payload']['arguments'])
                record['events'] = copy.deepcopy(gateway.events)
            record['receipt'] = outcome['receipt']
            record['transport_errors'] = outcome['transport_errors']
            record['effects'] = snapshot(port, token)
            # Host verifier checks persisted bytes independently of the reported HTTP snapshot.
            rows = [row.split('\t') for row in ledger.read_text().splitlines()]
            expected = [[e['effect_id'], e['order_id'], str(e['amount_minor_units']), e['currency'],
                         e['refund_scope'], e['idempotency_key_sha256'], e['committed_at']]
                        for e in record['effects']]
            if rows != expected: raise IntegrityError('Disk/HTTP ledger disagreement')
            verify_events(record['events'], record['effects'], plan['rule'], record['transport_errors'])
            (out / (label + '.tsv')).write_bytes(ledger.read_bytes())
        finally: runtime.stop_java(name, log)
        # New process, same world ledger, verifies graceful-restart reconstruction.
        guard.verify('before_restart:' + label)
        name, port = runtime.start_java(jars[j], ledger_dir, token, log)
        try:
            record['restart_recovered'] = snapshot(port, token) == record['effects']
            if not record['restart_recovered']: raise IntegrityError('Restart recovery mismatch')
        finally: runtime.stop_java(name, log)
    record['oracle_pass'] = check(record['effects'], plan['fixture'])
    record['status'] = 'completed'
    record['runtime_seconds'] = time.monotonic() - started
    return record


def run():
    out = ROOT / 'evidence-g6'; out.mkdir(exist_ok=True)
    if any(out.iterdir()): raise RuntimeError('Evidence directory must be empty')
    started = time.monotonic(); commit = revision()
    java, python = variants()
    records = []; agent = None; investigator = None
    def save(name, data): (out / name).write_text(json.dumps(data, indent=2, sort_keys=True))
    save('run-status.json', {'status': 'started', 'commit': commit, 'policy': POLICY})
    with tempfile.TemporaryDirectory(prefix='wheel-g6-') as temporary:
        scratch = Path(temporary)
        runtime = DockerRuntime(ROOT, scratch)
        try:
            images = runtime.prepare()
            isolation = runtime.probe()
            save('isolation-probes.json', isolation)
            jars = build_jars(java, scratch)
            save('build-hashes.json', {k: digest(v.read_bytes()) for k, v in jars.items()})
            # Only genuine provider calls. Container/build/probe errors precede spending.
            agent = MetaAgent(max_calls=52)
            agent.trace_path = out / 'model-traces.json'; agent.preflight_path = out / 'preflight.json'
            investigator = Investigator(agent.client, out / 'investigator-traces.json', max_calls=24)
            proposals = {}; decisions = {}; views = {}; scenarios = []
            for case in ('M1', 'M2', 'B1', 'B2'):
                views[case] = source_view(case, java, python)
                changed = DOMAIN if case in ('M1', 'B1') else CLIENT
                try:
                    proposal = investigator.investigate(views[case], changed,
                        (2500, 7500) if case in ('M1', 'B1') else (7500,))
                    decisions[case] = {'status': 'accepted'}
                except InvestigatorAbstained:
                    decisions[case] = {'status': 'abstained'}
                    if case in ('M1', 'M2'): raise
                    # Predeclared benign stress control, inherited before ANY world executes.
                    parent = 'M1' if case == 'B1' else 'M2'
                    proposal = copy.deepcopy(proposals[parent])
                    decisions[case]['control_origin'] = 'inherited_' + parent + '_after_abstention'
                proposals[case] = proposal
                scenarios.append({'case': case, 'amount': proposal['amount_minor_units'],
                                  'customer_message': proposal['customer_message']})
                save('investigation-decisions.json', decisions)
            save('investigator-proposals.json', proposals); save('source-snapshots.json', views)
            agent.scenarios = scenarios
            seeds = agent.prepare()
            plans = []
            for case in proposals:
                for mode in ('selected', 'no_fault'):
                    plans.append(make_plan(case, proposals[case], source_hashes(views[case]), seeds[case], mode))
            save('protected-fixtures.json', {p['id']: p['fixture'] for p in plans})
            save('tool_intent_seed.json', seeds)
            paths = sorted(set((ROOT / 'wheel').glob('*.py')) | set((ROOT / JAVA / 'src').rglob('*.*')) |
                           {ROOT / JAVA / 'pom.xml', ROOT / CLIENT, ROOT / 'services/support-agent-python/pyproject.toml'})
            frozen = {'commit': commit, 'policy': POLICY, 'trials': TRIALS,
                      'locked_at': datetime.now(timezone.utc).isoformat(), 'plans': plans,
                      'images': images, 'isolation': isolation, 'decisions': decisions,
                      'build_hashes': {k: digest(v.read_bytes()) for k, v in jars.items()},
                      'source_hashes': {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in paths},
                      'evidence_inputs': {p.name: digest(p.read_bytes()) for p in out.iterdir()
                                          if p.name != 'run-status.json'},
                      'model': {'id': 'muse-spark-1.3', 'support_request_limit': 52, 'investigator_request_limit': 24}}
            save('locked_experiment.json', frozen)
            plan_bytes = (out / 'locked_experiment.json').read_bytes()
            plan_hash = digest(plan_bytes)
            (out / 'locked_experiment.sha256').write_text(plan_hash + '\n')
            guard = PlanGuard(out / 'locked_experiment.json', plan_bytes, paths)
            for path in jars.values(): guard.bind(path, path.read_bytes())
            for path in list(out.iterdir()):
                # Dynamic execution/continuation traces are checked separately at publication.
                if path.name not in ('model-traces.json', 'run-status.json'):
                    guard.bind(path, path.read_bytes())
            manifest = {'commit': commit, 'plan_hash': plan_hash, 'policy': POLICY, 'images': images,
                        'build_hashes': frozen['build_hashes']}
            outcomes = {}
            for plan in plans:
                plan_records = []
                for trial in range(TRIALS):
                    pair = []
                    for which in ('base', 'candidate'):
                        label = f'{plan["id"]}-{trial}-{which}'
                        try:
                            record = world(runtime, plan, trial, which, jars, java, python,
                                           out, scratch, guard, manifest)
                            guard.verify('before_continuation:' + label)
                            if agent.frozen != seeds: raise IntegrityError('Tool seed drift')
                            record['model_reply'] = agent.continue_world(plan['case'], record['receipt'])
                        except IntegrityError:
                            save('integrity-failure.json', {'label': label, 'status': 'analysis_error',
                                 'reason': 'integrity_or_parity_failure'})
                            raise  # Never aggregate a parity/tamper failure into a finding.
                        except Exception as error:
                            # Keep ALL failed attempts. Do not persist exception bodies or credentials.
                            if 'record' not in locals() or record.get('label') != label:
                                record = {'label': label, 'plan_id': plan['id'], 'trial': trial,
                                          'world': which, 'case': plan['case'], 'oracle_pass': None}
                            record['status'] = 'analysis_error'; record['error_type'] = type(error).__name__
                        records.append(record); plan_records.append(record); pair.append(record)
                        save('results.json', records)
                    if all(r['status'] == 'completed' for r in pair):
                        validate_pair(*pair, plan, manifest)
                outcomes[plan['id']] = summarize(plan_records)
                save('outcomes.json', outcomes)
            guard.verify('after_all_worlds')
            if json.loads((out / 'results.json').read_text()) != records:
                raise IntegrityError('Execution evidence drift')
            if agent.frozen != seeds: raise IntegrityError('Tool seed drift')
            if revision() != commit: raise IntegrityError('Wrong-branch drift before verdict')
            traces = json.loads((out / 'model-traces.json').read_text())
            if traces != agent.traces: raise IntegrityError('Model trace drift')
            # Bind finalized records/ledgers/logs and preserve their hashes for inspection.
            for path in out.iterdir():
                if path.name != 'run-status.json': guard.bind(path, path.read_bytes())
            guard.publish(out / 'summary.json', {
                'status': 'evaluated_g6', 'commit': commit, 'policy': POLICY, 'plan_hash': plan_hash,
                'worlds': len(records), 'outcomes': outcomes,
                'investigator_calls': investigator.calls, 'support_agent_calls': agent.calls,
                'wall_seconds': time.monotonic() - started,
                'usage': {'investigator': [t['usage'] for t in investigator.traces],
                          'support_agent': [t['usage'] for t in agent.traces]},
                'limits': ['known_seeded_cases_not_blind_discovery', 'no_competitor_superiority_claim',
                           'single_producer_append_ledger_not_transactional_database',
                           'container_kernel_and_trusted_host_not_adversarially_certified',
                           'full_order_runtime_only_partial_scope_counterexamples_offline']})
            save('evidence-hashes.json', {p.name: digest(p.read_bytes()) for p in out.iterdir()
                                         if p.name not in ('run-status.json', 'evidence-hashes.json')})
            if any(r['status'] != 'completed' for r in records):
                raise RuntimeError('One or more worlds failed; inspect all preserved results')
            save('run-status.json', {'status': 'completed', 'wall_seconds': time.monotonic() - started})
        except BaseException as error:
            save('run-status.json', {'status': 'analysis_error', 'error_type': type(error).__name__,
                 'commit': commit, 'worlds_recorded': len(records), 'wall_seconds': time.monotonic() - started,
                 'investigator_calls': investigator.calls if investigator else 0,
                 'support_agent_calls': agent.calls if agent else 0})
            raise
        finally: runtime.close()


if __name__ == '__main__':
    try: run()
    except Exception as error:
        print('G6 stopped: ' + type(error).__name__ + '; inspect preserved stage artifacts.')
        raise SystemExit(1) from None
