"""Portable reviewed-fixture replay. No new investigator calls or plan selection.

The expected manifest hash is mandatory and must come from an independently
trusted run/record. Hashes prove consistency with that root, not author trust.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import tempfile
import time

from wheel.experiment import ROOT, JAVA, DOMAIN, CLIENT, digest
from wheel.g6 import variants, source_view, build_jars, world, revision
from wheel.intake import inspect, fixture_commit, git
from wheel.isolation import DockerRuntime, docker
from wheel.meta_agent import fingerprint, validate_intent, MetaAgent
from wheel.plan_guard import IntegrityError, PlanGuard
from wheel.repeatability import POLICY, TRIALS, validate_pair, summarize

SCHEMA = 'refund-portable-replay-v1'
HEX = re.compile(r'[0-9a-f]{64}\Z')
CASES = ('M1', 'M2', 'B1', 'B2')
PROTECTED = ('wheel/verifier.py', 'wheel/proxy.py', 'wheel/wrapper_worker.py',
             'wheel/plan_guard.py', 'wheel/repeatability.py', 'wheel/meta_agent.py',
             'wheel/g6.py', 'wheel/isolation.py')
MAX_FILE = 768 * 1024 * 1024
MAX_TOTAL = 2 * 1024 * 1024 * 1024


def file_sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def bounded_json(path, limit=4 * 1024 * 1024):
    if Path(path).stat().st_size > limit: raise IntegrityError('JSON exceeds size bound')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise IntegrityError('Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique)


def safe_file(root, name):
    if not isinstance(name, str) or '\\' in name:
        raise IntegrityError('Invalid manifest path')
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(p in ('.', '..') for p in path.parts) or str(path) != name:
        raise IntegrityError('Unsafe manifest path')
    root = Path(root)
    if root.is_symlink(): raise IntegrityError('Symlink bundle root')
    target = root
    for part in path.parts:
        target = target / part
        if target.is_symlink(): raise IntegrityError('Symlink bundle entry')
    if not target.is_file(): raise IntegrityError('Missing bundle file: ' + name)
    return target


def expected_hash(path, expected):
    if not isinstance(expected, str) or not HEX.fullmatch(expected) or file_sha(path) != expected:
        raise IntegrityError('Expected hash mismatch')


def validate_plans(plans, java, python):
    if not isinstance(plans, list) or len(plans) != 8:
        raise IntegrityError('Eight original selected/no-fault plans required')
    ids = set()
    for plan in plans:
        if set(plan) != {'id', 'case', 'mode', 'changed_side', 'rule', 'fixture', 'seed', 'source_hashes'}:
            raise IntegrityError('Unexpected plan fields')
        case, mode = plan['case'], plan['mode']
        if case not in CASES or mode not in ('selected', 'no_fault') or plan['id'] != case + '-' + mode or plan['id'] in ids:
            raise IntegrityError('Unknown or duplicate plan identity')
        ids.add(plan['id'])
        side = 'java' if case in ('M1', 'B1') else 'python'
        if plan['changed_side'] != side: raise IntegrityError('Changed-side mismatch')
        amount = plan['fixture'].get('amount_minor_units')
        if (set(plan['fixture']) != {'order_id', 'amount_minor_units'} or
                plan['fixture']['order_id'] != 'ORD-SYN-TRIAL' or type(amount) is not int or
                amount not in ((2500, 7500) if side == 'java' else (7500,))):
            raise IntegrityError('Unsupported authorization fixture')
        rule = plan['rule']
        if (set(rule) != {'action', 'min', 'max'} or
                rule['action'] not in ('PASS_THROUGH', 'DROP_DOWNSTREAM_BEFORE_RESPONSE', 'REPLACE_DOWNSTREAM_STATUS_502') or
                type(rule['min']) is not int or type(rule['max']) is not int or
                not 1 <= rule['min'] <= amount <= rule['max'] <= 100000):
            raise IntegrityError('Unsupported intervention')
        if mode == 'no_fault' and rule['action'] != 'PASS_THROUGH':
            raise IntegrityError('No-fault control changed')
        view = source_view(case, java, python)
        hashes = {s: {v: digest(t.encode()) for v, t in view[p].items()}
                  for s, p in [('java', DOMAIN), ('python', CLIENT)]}
        if hashes != plan['source_hashes']: raise IntegrityError('Reviewed source hash mismatch')
        seed = plan['seed']; payload = seed['payload']
        if set(seed) != {'payload', 'sha256'} or fingerprint(payload) != seed['sha256']:
            raise IntegrityError('Frozen tool seed mismatch')
        if payload['authorization'] != plan['fixture']:
            raise IntegrityError('Seed/fixture mismatch')
        args = validate_intent(payload['messages'][-1], plan['fixture'])
        if args != payload['arguments'] or payload['messages'][-1]['tool_calls'][0]['id'] != payload['tool_call_id']:
            raise IntegrityError('Frozen intent does not match conversation')
    for case in CASES:
        selected = next(p for p in plans if p['id'] == case + '-selected')
        normal = next(p for p in plans if p['id'] == case + '-no_fault')
        for key in ('seed', 'fixture', 'source_hashes'):
            if selected[key] != normal[key]: raise IntegrityError('No-fault peer/input drift')


def load_g6(evidence, expected_plan):
    evidence = Path(evidence)
    path = safe_file(evidence, 'locked_experiment.json'); expected_hash(path, expected_plan)
    frozen = bounded_json(path)
    if frozen['policy'] != POLICY or frozen['trials'] != TRIALS:
        raise IntegrityError('Unsupported source policy/trial count')
    java, python = variants()
    validate_plans(frozen['plans'], java, python)
    for name in PROTECTED:
        if frozen['source_hashes'].get(name) != file_sha(ROOT / name):
            raise IntegrityError('Trusted engine/oracle version drift: ' + name)
    for name, sha in frozen['evidence_inputs'].items():
        if name == 'model-traces.json':
            # G6 froze four initial selections, then appended genuine continuations.
            traces = bounded_json(safe_file(evidence, name))
            initial_count = len({p['case'] for p in frozen['plans']})
            if digest(json.dumps(traces[:initial_count], indent=2).encode()) != sha:
                raise IntegrityError('Initial support-agent trace prefix changed')
        else:
            expected_hash(safe_file(evidence, name), sha)
    snapshots = bounded_json(safe_file(evidence, 'source-snapshots.json'))
    if snapshots != {case: source_view(case, java, python) for case in CASES}:
        raise IntegrityError('Unreviewed source snapshot')
    return frozen, java, python


def pack(evidence, expected_plan, output):
    evidence, output = Path(evidence).resolve(), Path(output).absolute()
    frozen, java, python = load_g6(evidence, expected_plan)  # Before Docker/build/network.
    engine_commit = revision()
    if output.exists(): raise IntegrityError('Bundle output must not exist')
    output.mkdir(parents=True)
    runtime = None
    try:
        origin = output / 'origin'; origin.mkdir()
        # Preserve the original plan/trace/ledger evidence, not only an index.
        for path in evidence.iterdir():
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
                raise IntegrityError('Unsupported source evidence entry')
            shutil.copyfile(path, origin / path.name)
        with tempfile.TemporaryDirectory(prefix='wheel-pack-') as directory:
            scratch = Path(directory)
            runtime = DockerRuntime(ROOT, scratch)
            images = runtime.prepare(); probes = runtime.probe()
            jars = build_jars(java, scratch)
            (output / 'jars').mkdir(); (output / 'images').mkdir()
            for name, jar in jars.items(): shutil.copyfile(jar, output / 'jars' / (name + '.jar'))
            for name, image in images.items():
                docker('save', '--output', output / 'images' / (name + '.tar'), image, timeout=300)
            records = {}; refs = []; namespace = secrets.token_hex(6)
            # Existing accepted source bytes become actual pinned Git revisions.
            # This is disclosed synthetic provenance, not an external developer PR.
            for case in CASES:
                side = 'java' if case in ('M1', 'B1') else 'python'
                path = DOMAIN if side == 'java' else CLIENT
                text = java[case] if side == 'java' else python[case]
                candidate = fixture_commit(ROOT, frozen['commit'], path, text, case)
                records[case] = inspect(ROOT, frozen['commit'], candidate, side)
                records[case]['provenance'] = 'synthetic_local_fixture_commit_from_saved_G6_source'
                ref = 'refs/codex-wheel/replay-' + namespace + '-' + case
                git(ROOT, 'update-ref', ref, candidate); refs.append(ref)
            try:
                git(ROOT, 'bundle', 'create', str(output / 'sources.bundle'), *refs)
            finally:
                for ref in refs: git(ROOT, 'update-ref', '-d', ref)
            (output / 'intake.json').write_text(json.dumps(records, indent=2, sort_keys=True))
            files = {p.relative_to(output).as_posix(): {'sha256': file_sha(p), 'bytes': p.stat().st_size}
                     for p in sorted(output.rglob('*')) if p.is_file()}
            manifest = {'schema': SCHEMA, 'engine_commit': engine_commit, 'policy': POLICY,
                'created_at': datetime.now(timezone.utc).isoformat(), 'trials': TRIALS,
                'original_g6_plan_sha256': expected_plan, 'plans': frozen['plans'],
                'images': images, 'build_hashes': {name: file_sha(output / 'jars' / (name + '.jar')) for name in jars},
                'protected_engine': {name: file_sha(ROOT / name) for name in PROTECTED},
                'isolation_probes': probes, 'intake': {c: {k: v for k, v in item.items() if k not in ('java', 'python')}
                                                      for c, item in records.items()},
                'files': files, 'reconstruction': 'G6_source_plan_seed_reused; binaries_and_runtime_rebuilt_once_then_archived',
                'model_policy': 'no_new_inference_by_default; optional_live_continuations_only'}
            (output / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True))
            sha = file_sha(output / 'manifest.json')
            (output / 'manifest.sha256').write_text(sha + '\n')
            print(json.dumps({'status': 'packed', 'expected_manifest_sha256': sha,
                              'files': len(files), 'images': images}, sort_keys=True), flush=True)
            return sha
    finally:
        if runtime: runtime.close()


def verify(bundle, expected_manifest):
    bundle = Path(bundle).absolute()
    manifest_path = safe_file(bundle, 'manifest.json'); expected_hash(manifest_path, expected_manifest)
    data = bounded_json(manifest_path)
    if data['schema'] != SCHEMA or data['policy'] != POLICY or data['trials'] != TRIALS:
        raise IntegrityError('Unsupported replay policy')
    if data['engine_commit'] != revision():
        raise IntegrityError('Replay requires the exact pinned runner commit')
    if data['protected_engine'] != {name: file_sha(ROOT / name) for name in PROTECTED}:
        raise IntegrityError('Trusted verifier/runner changed')
    java, python = variants(); validate_plans(data['plans'], java, python)
    files = data['files']
    if not isinstance(files, dict) or not 5 <= len(files) <= 512:
        raise IntegrityError('Invalid bundle inventory')
    total = 0
    for name, item in files.items():
        path = safe_file(bundle, name)
        if set(item) != {'sha256', 'bytes'} or type(item['bytes']) is not int or not 0 <= item['bytes'] <= MAX_FILE:
            raise IntegrityError('Invalid file metadata')
        total += item['bytes']
        if total > MAX_TOTAL or path.stat().st_size != item['bytes']:
            raise IntegrityError('Bundle size mismatch')
        expected_hash(path, item['sha256'])
    actual = {p.relative_to(bundle).as_posix() for p in bundle.rglob('*') if p.is_file() or p.is_symlink()}
    if actual != set(files) | {'manifest.json', 'manifest.sha256'}:
        raise IntegrityError('Unexpected or missing bundle entry')
    if safe_file(bundle, 'manifest.sha256').read_text().strip() != expected_manifest:
        raise IntegrityError('Manifest sidecar mismatch')
    original = bounded_json(safe_file(bundle, 'origin/locked_experiment.json'))
    expected_hash(bundle / 'origin/locked_experiment.json', data['original_g6_plan_sha256'])
    if original['plans'] != data['plans']:
        raise IntegrityError('Replay plan differs from original accepted experiment')
    # Revalidate committed source content against the reviewed policy, offline.
    with tempfile.TemporaryDirectory(prefix='wheel-intake-') as directory:
        repo = Path(directory) / 'source.git'
        git(ROOT, 'clone', '--mirror', '--quiet', str(bundle / 'sources.bundle'), str(repo))
        recorded = bounded_json(safe_file(bundle, 'intake.json'))
        for case in CASES:
            item = data['intake'][case]
            observed = inspect(repo, item['base_commit'], item['candidate_commit'], item['changed_side'])
            if observed['case'] != case or observed != {k: v for k, v in recorded[case].items() if k != 'provenance'}:
                raise IntegrityError('Pinned source evidence mismatch')
            if {k: v for k, v in recorded[case].items() if k not in ('java', 'python')} != item:
                raise IntegrityError('Manifest/intake disagreement')
    return data, java, python


class ArchivedRuntime(DockerRuntime):
    def restore(self, bundle, manifest):
        docker('info')
        for name in ('java', 'python'):
            docker('load', '--input', Path(bundle) / 'images' / (name + '.tar'), timeout=300)
            image = manifest['images'][name]
            if json.loads(docker('image', 'inspect', image).stdout)[0]['Id'] != image:
                raise IntegrityError('Loaded runtime image differs from locked ID')
        self.images = copy.deepcopy(manifest['images'])
        docker('network', 'create', '--internal', self.network)
        return self.probe()


def execute(bundle, expected_manifest, output, live_continuations=False):
    started = time.monotonic(); bundle = Path(bundle).absolute(); output = Path(output).absolute()
    data, java, python = verify(bundle, expected_manifest)  # No Docker/network before all checks.
    if output.exists(): raise IntegrityError('Replay output must not exist')
    output.mkdir(parents=True)
    records = []; agent = None
    def save(name, value): (output / name).write_text(json.dumps(value, indent=2, sort_keys=True))
    save('run-status.json', {'status': 'started', 'mode': 'live_continuations' if live_continuations else 'deterministic_replay'})
    with tempfile.TemporaryDirectory(prefix='wheel-replay-') as directory:
        runtime = ArchivedRuntime(ROOT, Path(directory))
        try:
            probes = runtime.restore(bundle, data)
            if live_continuations:
                agent = MetaAgent(max_calls=48)
                agent.trace_path = output / 'fresh-model-traces.json'
                agent.frozen = {p['case']: copy.deepcopy(p['seed']) for p in data['plans']}
            jars = {name: bundle / 'jars' / (name + '.jar') for name in ('base', 'M1', 'B1')}
            for name, jar in jars.items(): expected_hash(jar, data['build_hashes'][name])
            guard = PlanGuard(bundle / 'manifest.json', (bundle / 'manifest.json').read_bytes(),
                              [ROOT / name for name in PROTECTED])
            for jar in jars.values(): guard.bind(jar, jar.read_bytes())
            locked_plans = copy.deepcopy(data['plans'])
            manifest = {'commit': data['engine_commit'], 'plan_hash': expected_manifest,
                        'policy': POLICY, 'images': data['images'], 'build_hashes': data['build_hashes']}
            outcomes = {}
            for plan in locked_plans:
                current = []
                for trial in range(TRIALS):
                    pair = []
                    for which in ('base', 'candidate'):
                        label = f'{plan["id"]}-{trial}-{which}'
                        record = None
                        try:
                            if data['plans'] != locked_plans: raise IntegrityError('In-memory replay plan drift')
                            record = world(runtime, plan, trial, which, jars, java, python,
                                           output, Path(directory), guard, manifest)
                            guard.verify('after_world:' + label)
                            if agent:
                                if agent.frozen[plan['case']] != plan['seed']: raise IntegrityError('Continuation seed drift')
                                record['model_reply'] = agent.continue_world(plan['case'], record['receipt'])
                                record['message_origin'] = 'fresh_Meta_continuation'
                            else:
                                record['model_reply'] = None
                                record['message_origin'] = 'not_requested; original_messages_in_origin_evidence_only'
                        except Exception as error:
                            record = record or {'label': label, 'plan_id': plan['id'], 'case': plan['case'],
                                                'world': which, 'trial': trial, 'oracle_pass': None}
                            record['status'] = 'analysis_error'; record['error_type'] = type(error).__name__
                            records.append(record); save('results.json', records)
                            if isinstance(error, IntegrityError): raise
                        else:
                            records.append(record); save('results.json', records)
                        current.append(record); pair.append(record)
                        print('Replay: ' + label + ' ' + record['status'], flush=True)
                    if all(r['status'] == 'completed' for r in pair): validate_pair(*pair, plan, manifest)
                outcomes[plan['id']] = summarize(current); save('outcomes.json', outcomes)
            if bounded_json(output / 'results.json') != records:
                raise IntegrityError('Replay result evidence changed')
            guard.publish(output / 'summary.json', {'status': 'evaluated_replay',
                'mode': 'fresh_continuations' if agent else 'deterministic_tool_backend_replay',
                'source_manifest_sha256': expected_manifest, 'original_plan_sha256': data['original_g6_plan_sha256'],
                'worlds': len(records), 'outcomes': outcomes, 'isolation_probes': probes,
                'investigator_calls': 0, 'fresh_support_agent_calls': agent.calls if agent else 0,
                'wall_seconds': time.monotonic() - started,
                'limits': ['reviewed_refund_fixture_only', 'known_seeded_changes',
                           'producer_owned_ledger', 'G6_runtime_reconstructed_at_pack_then_immutably_archived']})
            if any(r['status'] != 'completed' for r in records):
                raise RuntimeError('Replay contained failed worlds; inspect every recorded outcome')
            save('run-status.json', {'status': 'completed', 'worlds': len(records),
                                    'wall_seconds': time.monotonic() - started})
        except BaseException as error:
            save('run-status.json', {'status': 'analysis_error', 'error_type': type(error).__name__,
                                    'worlds_recorded': len(records)})
            raise
        finally: runtime.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    packing = commands.add_parser('pack')
    packing.add_argument('--evidence', type=Path, required=True)
    packing.add_argument('--expected-plan-sha256', required=True)
    packing.add_argument('--output', type=Path, required=True)
    for name in ('verify', 'run'):
        command = commands.add_parser(name)
        command.add_argument('--bundle', type=Path, required=True)
        command.add_argument('--expected-manifest-sha256', required=True)
        if name == 'run':
            command.add_argument('--output', type=Path, required=True)
            command.add_argument('--live-continuations', action='store_true')
    args = parser.parse_args()
    if args.command == 'pack': pack(args.evidence, args.expected_plan_sha256, args.output)
    elif args.command == 'verify':
        data, _, _ = verify(args.bundle, args.expected_manifest_sha256)
        print(json.dumps({'status': 'verified_before_execution', 'plans': len(data['plans'])}))
    else: execute(args.bundle, args.expected_manifest_sha256, args.output, args.live_continuations)


if __name__ == '__main__':
    try: main()
    except Exception as error:
        print(json.dumps({'status': 'analysis_error', 'error_type': type(error).__name__}))
        raise SystemExit(1) from None
