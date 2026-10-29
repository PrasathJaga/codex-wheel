"""Offline pinned-source and replay integrity tests. Fake binaries are explicit."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
from unittest.mock import Mock, patch

import pytest

from wheel import intake, replay
from wheel.experiment import ROOT, JAVA, DOMAIN, CLIENT, digest
from wheel.g6 import variants, source_view, source_hashes
from wheel.meta_agent import fingerprint
from wheel.plan_guard import IntegrityError
from wheel.repeatability import POLICY, make_plan


def seed(amount):
    args = {'order_id': 'ORD-SYN-TRIAL', 'amount_minor_units': amount,
            'currency': 'USD', 'refund_scope': 'full_order'}
    assistant = {'role': 'assistant', 'tool_calls': [{'id': 'fake_offline_call', 'type': 'function',
                    'function': {'name': 'issue_refund', 'arguments': json.dumps(args)}}]}
    payload = {'messages': [{'role': 'user', 'content': 'Synthetic offline unit-test fixture'}, assistant],
               'arguments': args, 'authorization': {'order_id': 'ORD-SYN-TRIAL', 'amount_minor_units': amount},
               'tool_call_id': 'fake_offline_call', 'operation_context': 'fake_unit_test'}
    return {'payload': payload, 'sha256': fingerprint(payload)}


def plans():
    java, python = variants(); result = []
    for case in replay.CASES:
        amount = 2500 if case in ('M1', 'B1') else 7500
        proposal = {'amount_minor_units': amount, 'fault': {'action': 'DROP_DOWNSTREAM_BEFORE_RESPONSE'
                    if amount == 2500 else 'REPLACE_DOWNSTREAM_STATUS_502', 'min': amount, 'max': amount}}
        for mode in ('selected', 'no_fault'):
            result.append(make_plan(case, proposal, source_hashes(source_view(case, java, python)), seed(amount), mode))
    return result


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / 'repo'; root.mkdir()
    shutil.copytree(ROOT / JAVA / 'src', root / JAVA / 'src')
    for name in (JAVA + '/pom.xml', CLIENT, 'services/support-agent-python/pyproject.toml'):
        target = root / name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    intake.git(root, 'init', '--quiet')
    intake.git(root, 'config', 'user.name', 'Offline Fixture')
    intake.git(root, 'config', 'user.email', 'fixture@codex-wheel.invalid')
    intake.git(root, 'add', '.')
    intake.git(root, 'commit', '--quiet', '-m', 'Offline reviewed baseline')
    return root, intake.git(root, 'rev-parse', 'HEAD').decode().strip()


def test_full_pinned_commits_are_read_without_switching_worktree(repo):
    root, base = repo; java, python = variants()
    for case in replay.CASES:
        side = 'java' if case in ('M1', 'B1') else 'python'
        path = DOMAIN if side == 'java' else CLIENT
        candidate = intake.fixture_commit(root, base, path, java[case] if side == 'java' else python[case], case)
        result = intake.inspect(root, base, candidate, side)
        assert result['case'] == case
        assert result['fixed_peer_commit'] == base
        assert intake.git(root, 'rev-parse', 'HEAD').decode().strip() == base
        assert not intake.git(root, 'status', '--porcelain')
    for bad in ('HEAD', base[:12], '../source', 'a' * 39, 'A' * 40):
        with pytest.raises(IntegrityError): intake.inspect(root, bad, candidate, side)


def test_unreviewed_code_wrong_peer_and_build_changes_are_unsupported(repo):
    root, base = repo; java, python = variants()
    bad = intake.fixture_commit(root, base, DOMAIN, java['base'] + '\n// unreviewed\n', 'bad')
    with pytest.raises(IntegrityError, match='not been reviewed'): intake.inspect(root, base, bad, 'java')
    m1 = intake.fixture_commit(root, base, DOMAIN, java['M1'], 'M1')
    both = intake.fixture_commit(root, m1, CLIENT, python['M2'], 'both')
    with pytest.raises(IntegrityError, match='one supported'): intake.inspect(root, base, both, 'java')
    changed_build = intake.fixture_commit(root, base, JAVA + '/pom.xml', (ROOT / JAVA / 'pom.xml').read_text() + '\n', 'build')
    pair = intake.fixture_commit(root, changed_build, DOMAIN, java['M1'], 'M1')
    with pytest.raises(IntegrityError, match='build or producer'): intake.inspect(root, changed_build, pair, 'java')
    with pytest.raises(IntegrityError): intake.inspect(root, base, m1, 'python')


def test_plan_seed_fixture_source_and_intervention_checks():
    java, python = variants(); original = plans()
    replay.validate_plans(original, java, python)
    for key, value in [('case', '../bad'), ('changed_side', 'python'),
                       ('fixture', {'order_id': 'other', 'amount_minor_units': 2500}),
                       ('rule', {'action': 'SHELL', 'min': 1, 'max': 2500}),
                       ('source_hashes', {})]:
        altered = copy.deepcopy(original); altered[0][key] = value
        with pytest.raises(IntegrityError): replay.validate_plans(altered, java, python)
    altered = copy.deepcopy(original); altered[0]['seed']['payload']['arguments']['amount_minor_units'] = 1
    with pytest.raises(IntegrityError): replay.validate_plans(altered, java, python)
    altered = copy.deepcopy(original); altered[1]['rule']['action'] = 'REPLACE_DOWNSTREAM_STATUS_502'
    with pytest.raises(IntegrityError): replay.validate_plans(altered, java, python)
    with pytest.raises(IntegrityError): replay.validate_plans(original[:-1], java, python)


def test_duplicate_json_symlinks_and_unsafe_paths_rejected(tmp_path):
    (tmp_path / 'file').write_text('value')
    (tmp_path / 'link').symlink_to(tmp_path / 'file')
    for path in ('../file', '/file', 'link', 'a/../file', './file', 'a\\file'):
        with pytest.raises(IntegrityError): replay.safe_file(tmp_path, path)
    (tmp_path / 'duplicate.json').write_text('{"a":1,"a":2}')
    with pytest.raises(IntegrityError): replay.bounded_json(tmp_path / 'duplicate.json')


def test_g6_validation_precedes_runtime_and_build(tmp_path):
    evidence = tmp_path / 'evidence'; evidence.mkdir()
    (evidence / 'locked_experiment.json').write_text('{}')
    with patch.object(replay, 'DockerRuntime') as runtime, patch.object(replay, 'build_jars') as build:
        with pytest.raises(IntegrityError): replay.pack(evidence, '0' * 64, tmp_path / 'output')
        runtime.assert_not_called(); build.assert_not_called()


@pytest.fixture
def bundle(tmp_path, repo):
    """Real Git provenance, fake archives/JARs; verification only, never executed."""
    root, base = repo; target = tmp_path / 'bundle'; target.mkdir()
    java, python = variants(); entries = {}; refs = []
    for case in replay.CASES:
        side = 'java' if case in ('M1', 'B1') else 'python'
        path = DOMAIN if side == 'java' else CLIENT
        candidate = intake.fixture_commit(root, base, path, java[case] if side == 'java' else python[case], case)
        entries[case] = intake.inspect(root, base, candidate, side)
        entries[case]['provenance'] = 'synthetic_local_fixture_commit_from_saved_G6_source'
        ref = 'refs/tests/' + case; intake.git(root, 'update-ref', ref, candidate); refs.append(ref)
    intake.git(root, 'bundle', 'create', str(target / 'sources.bundle'), *refs)
    (target / 'intake.json').write_text(json.dumps(entries))
    (target / 'origin').mkdir()
    original = {'plans': plans()}
    (target / 'origin/locked_experiment.json').write_text(json.dumps(original))
    for side in ('java', 'python'):
        (target / 'images').mkdir(exist_ok=True)
        (target / 'images' / (side + '.tar')).write_bytes(b'OFFLINE FAKE ARCHIVE; NEVER LOADED')
    for name in ('base', 'M1', 'B1'):
        (target / 'jars').mkdir(exist_ok=True)
        (target / 'jars' / (name + '.jar')).write_bytes(b'OFFLINE FAKE JAR; NEVER EXECUTED')
    data = {'schema': replay.SCHEMA, 'engine_commit': base, 'policy': POLICY, 'trials': 3,
            'protected_engine': {name: replay.file_sha(ROOT / name) for name in replay.PROTECTED},
            'plans': original['plans'], 'original_g6_plan_sha256': replay.file_sha(target / 'origin/locked_experiment.json'),
            'intake': {case: {k: v for k, v in item.items() if k not in ('java', 'python')} for case, item in entries.items()},
            'images': {'java': 'fake-java', 'python': 'fake-python'},
            'build_hashes': {name: replay.file_sha(target / 'jars' / (name + '.jar')) for name in ('base', 'M1', 'B1')}}
    data['files'] = {p.relative_to(target).as_posix(): {'bytes': p.stat().st_size, 'sha256': replay.file_sha(p)}
                     for p in target.rglob('*') if p.is_file()}
    (target / 'manifest.json').write_text(json.dumps(data))
    expected = replay.file_sha(target / 'manifest.json')
    (target / 'manifest.sha256').write_text(expected + '\n')
    return target, expected, base, data


def test_complete_bundle_can_be_verified_without_docker_network_or_models(bundle):
    folder, expected, commit, data = bundle
    with patch.object(replay, 'revision', return_value=commit), patch.object(replay, 'docker') as docker:
        verified, _, _ = replay.verify(folder, expected)
        assert verified['plans'] == data['plans']
        docker.assert_not_called()


def test_manifest_rewrite_sidecar_cannot_reauthorize_tampering(bundle):
    folder, expected, commit, data = bundle
    data['plans'][0]['fixture']['amount_minor_units'] = 7500
    (folder / 'manifest.json').write_text(json.dumps(data))
    (folder / 'manifest.sha256').write_text(replay.file_sha(folder / 'manifest.json'))
    with patch.object(replay, 'revision', return_value=commit), patch.object(replay, 'ArchivedRuntime') as runtime:
        with pytest.raises(IntegrityError): replay.execute(folder, expected, folder.parent / 'output')
        runtime.assert_not_called()


@pytest.mark.parametrize('name', ['jars/M1.jar', 'images/python.tar', 'intake.json', 'sources.bundle', 'origin/locked_experiment.json'])
def test_any_locked_file_change_fails_before_runtime(bundle, name):
    folder, expected, commit, data = bundle
    (folder / name).write_bytes(b'changed')
    with patch.object(replay, 'revision', return_value=commit), patch.object(replay, 'ArchivedRuntime') as runtime:
        with pytest.raises(IntegrityError): replay.execute(folder, expected, folder.parent / 'out')
        runtime.assert_not_called()


def test_wrong_runner_missing_extra_file_and_sidecar_rejected(bundle):
    folder, expected, commit, _ = bundle
    with patch.object(replay, 'revision', return_value='b' * 40):
        with pytest.raises(IntegrityError, match='pinned runner'): replay.verify(folder, expected)
    with patch.object(replay, 'revision', return_value=commit):
        (folder / 'unexpected').write_text('unexpected')
        with pytest.raises(IntegrityError, match='Unexpected'): replay.verify(folder, expected)
        (folder / 'unexpected').unlink()
        (folder / 'manifest.sha256').write_text('0' * 64)
        with pytest.raises(IntegrityError, match='sidecar'): replay.verify(folder, expected)


def test_default_execution_does_not_instantiate_a_model_or_invent_messages(bundle):
    folder, expected, commit, data = bundle
    java, python = variants()
    def fake_world(runtime, plan, trial, which, jars, j, p, output, scratch, guard, manifest):
        candidate = which == 'candidate'
        count = 2 if candidate and plan['case'] in ('M1', 'M2') and plan['mode'] == 'selected' else 1
        return {'label': f'{plan["id"]}-{trial}-{which}', 'plan_id': plan['id'],
                'case': plan['case'], 'world': which, 'trial': trial, 'status': 'completed',
                'plan_hash': expected, 'fixture_sha256': fingerprint(plan['fixture']),
                'seed_sha256': fingerprint(plan['seed']), 'rule_sha256': fingerprint(plan['rule']),
                'policy': POLICY, 'images': data['images'], 'reset_empty': True, 'restart_recovered': True,
                'java_sha256': plan['source_hashes']['java'][which],
                'python_sha256': plan['source_hashes']['python'][which],
                'jar_sha256': data['build_hashes'][plan['case'] if candidate and plan['changed_side'] == 'java' else 'base'],
                'oracle_pass': count == 1, 'effects': [{'amount_minor_units': plan['fixture']['amount_minor_units']}] * count,
                'events': [{'key_sha256': 'fake', 'action': plan['rule']['action']}], 'transport_errors': [],
                'receipt': {'status': 'FAKE_OFFLINE_UNIT_TEST'}}
    output = folder.parent / 'output'
    with patch.object(replay, 'verify', return_value=(data, java, python)), \
            patch.object(replay, 'world', side_effect=fake_world), patch.object(replay, 'MetaAgent') as model, \
            patch.object(replay, 'ArchivedRuntime') as runtime:
        runtime.return_value.images = data['images']
        runtime.return_value.restore.return_value = {'offline_fake_probe': True}
        replay.execute(folder, expected, output)
        model.assert_not_called()
    results = json.loads((output / 'results.json').read_text())
    assert len(results) == 48 and all(r['model_reply'] is None for r in results)
    assert json.loads((output / 'summary.json').read_text())['fresh_support_agent_calls'] == 0


def test_caller_supplied_revision_pairs_are_admitted_before_docker(tmp_path, repo):
    root, base = repo; java, python = variants(); pairs = {}
    for case in replay.CASES:
        side = 'java' if case in ('M1', 'B1') else 'python'
        candidate = intake.fixture_commit(root, base, DOMAIN if side == 'java' else CLIENT,
                                         java[case] if side == 'java' else python[case], case)
        pairs[case] = {'base': base, 'candidate': candidate, 'changed_side': side}
    path = tmp_path / 'requested.json'; path.write_text(json.dumps(pairs))
    evidence = tmp_path / 'origin'; evidence.mkdir()
    frozen = {'commit': base, 'plans': plans()}
    with patch.object(replay, 'load_g6', return_value=(frozen, java, python)), \
            patch.object(replay, 'revision', return_value=base), patch.object(replay, 'DockerRuntime') as runtime:
        runtime.return_value.prepare.side_effect = RuntimeError('offline stop before actual Docker')
        with pytest.raises(RuntimeError, match='offline stop'):
            replay.pack(evidence, '0' * 64, tmp_path / 'out', path, root)
        runtime.return_value.prepare.assert_called_once()
    pairs['M1']['candidate'] = base  # No change; cannot reach build/runtime.
    path.write_text(json.dumps(pairs))
    with patch.object(replay, 'load_g6', return_value=(frozen, java, python)), \
            patch.object(replay, 'revision', return_value=base), patch.object(replay, 'DockerRuntime') as runtime:
        with pytest.raises(IntegrityError): replay.pack(evidence, '0' * 64, tmp_path / 'bad', path, root)
        runtime.assert_not_called()
