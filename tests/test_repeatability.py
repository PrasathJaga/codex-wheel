"""Offline G6 verdict/parity counterexamples; no inference or containers claimed."""
import copy
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch
import httpx
import pytest

from wheel import g6
from wheel.isolation import UnixBroker
from wheel.meta_agent import fingerprint, MetaAgent
from wheel.plan_guard import IntegrityError
from wheel.repeatability import summarize, validate_pair, make_plan, POLICY
from wheel.verifier import check_operations


def proposal():
    return {'amount_minor_units': 2500, 'fault': {
        'action': 'DROP_DOWNSTREAM_BEFORE_RESPONSE', 'min': 2500, 'max': 2500}}


def fixture_records(candidate_pass=False):
    plan = make_plan('M1', proposal(), {
        'java': {'base': 'j0', 'candidate': 'j1'},
        'python': {'base': 'p0', 'candidate': 'p0'}}, {'payload': 'fake-only'})
    manifest = {'plan_hash': 'frozen', 'policy': POLICY, 'images': {'java': 'j-image', 'python': 'p-image'}, 'build_hashes': {'base': 'jar0', 'M1': 'jar1'}}
    records = []
    for trial in range(3):
        for world in ('base', 'candidate'):
            passed = world == 'base' or candidate_pass
            n = 1 if passed else 2
            records.append({'trial': trial, 'world': world, 'status': 'completed',
                'oracle_pass': passed, 'plan_hash': 'frozen',
                'fixture_sha256': fingerprint(plan['fixture']), 'seed_sha256': fingerprint(plan['seed']),
                'rule_sha256': fingerprint(plan['rule']), 'policy': POLICY, 'images': manifest['images'],
                'reset_empty': True, 'restart_recovered': True,
                'java_sha256': 'j0' if world == 'base' else 'j1', 'python_sha256': 'p0',
                'jar_sha256': 'jar0' if world == 'base' else 'jar1',
                'effects': [{'amount_minor_units': 2500}] * n,
                'events': [{'key_sha256': 'same', 'action': a} for a in
                           ('DROP_DOWNSTREAM_BEFORE_RESPONSE', 'PASS_THROUGH')],
                'transport_errors': ['RemoteProtocolError']})
    return plan, manifest, records


def test_three_of_three_required_and_model_prose_ignored():
    _, _, rows = fixture_records()
    for row in rows: row['model_reply'] = {'content': 'Everything is safe'}
    assert summarize(rows)['verdict'] == 'reproduced_regression'
    rows[-1] = copy.deepcopy(rows[-2]); rows[-1]['world'] = 'candidate'
    result = summarize(rows)
    assert result['verdict'] == 'inconclusive'
    assert result['candidate_passes'] == 1
    with pytest.raises(ValueError): summarize(rows, trials=2)


def test_baseline_failure_and_infrastructure_failure_never_become_regressions():
    _, _, rows = fixture_records()
    rows[0]['oracle_pass'] = False
    assert summarize(rows)['reason'] == 'baseline_invariant_failed'
    rows[0]['status'] = 'analysis_error'
    assert summarize(rows)['verdict'] == 'analysis_error'
    assert summarize(rows[:-1])['verdict'] == 'inconclusive'
    assert summarize(rows + [rows[0]])['verdict'] == 'inconclusive'


def test_consistent_pass_and_mixed_mechanisms():
    _, _, rows = fixture_records(candidate_pass=True)
    assert summarize(rows)['verdict'] == 'not_reproduced'
    _, _, rows = fixture_records()
    rows[-1]['events'][1]['key_sha256'] = 'new-key'
    assert summarize(rows)['verdict'] == 'inconclusive'


def test_actual_peer_plan_fixture_policy_image_seed_and_source_drift_rejected():
    plan, manifest, rows = fixture_records()
    validate_pair(rows[0], rows[1], plan, manifest)
    for key in ('plan_hash', 'fixture_sha256', 'rule_sha256', 'seed_sha256', 'policy',
                'images', 'jar_sha256', 'java_sha256', 'python_sha256', 'reset_empty', 'restart_recovered', 'trial', 'world'):
        bad = copy.deepcopy(rows[1]); bad[key] = 'drift'
        with pytest.raises(IntegrityError): validate_pair(rows[0], bad, plan, manifest)
    # Even a matching recorded hash cannot legitimize an altered fixed peer.
    plan['source_hashes']['python']['candidate'] = 'changed-peer'
    rows[1]['python_sha256'] = 'changed-peer'
    with pytest.raises(IntegrityError): validate_pair(rows[0], rows[1], plan, manifest)


def test_no_fault_control_does_not_mutate_original_plan_or_seed():
    p = proposal(); seed = {'payload': {'arguments': {'amount_minor_units': 2500}}}
    plan = make_plan('M1', p, {}, seed, mode='no_fault')
    assert plan['rule']['action'] == 'PASS_THROUGH'
    assert p['fault']['action'] == 'DROP_DOWNSTREAM_BEFORE_RESPONSE'
    seed['payload']['arguments']['amount_minor_units'] = 1
    assert plan['seed']['payload']['arguments']['amount_minor_units'] == 2500


def test_post_commit_rule_and_actual_evidence_are_required():
    events = [{'upstream_status': 200, 'action': 'REPLACE_DOWNSTREAM_STATUS_502',
               'commit_evidence': {'effect_id': 'e1', 'rows_before_downstream_action': 1},
               'upstream_body': {'refund_effect_id': 'e1'}},
              {'upstream_status': 200, 'action': 'PASS_THROUGH',
               'commit_evidence': {'effect_id': 'e1', 'rows_before_downstream_action': 1},
               'upstream_body': {'refund_effect_id': 'e1'}}]
    effects = [{'effect_id': 'e1'}]; rule = {'action': 'REPLACE_DOWNSTREAM_STATUS_502'}
    g6.verify_events(events, effects, rule, [])
    for key, value in [('upstream_status', 500), ('commit_evidence', None), ('action', 'PASS_THROUGH')]:
        bad = copy.deepcopy(events); bad[0][key] = value
        with pytest.raises(IntegrityError): g6.verify_events(bad, effects, rule, [])
    with pytest.raises(IntegrityError): g6.verify_events(events, [], rule, [])
    with pytest.raises(IntegrityError): g6.verify_events(events, effects, rule, ['unexpected'])


def test_two_legitimate_partials_on_one_order_are_distinct_authorizations():
    auth = [dict(authorization_id=k, order_id='same-order', currency='USD',
                 refund_scope='partial', amount_minor_units=amount)
            for k, amount in [('a', 1000), ('b', 1500)]]
    assert check_operations(copy.deepcopy(auth), auth)
    # A global one-row-per-order oracle would incorrectly reject this valid case.
    assert not check_operations(auth + [auth[0]], auth)
    bad = copy.deepcopy(auth); bad[1]['authorization_id'] = 'a'
    assert not check_operations(bad, auth)
    bad = copy.deepcopy(auth); bad[0]['amount_minor_units'] = 999
    assert not check_operations(bad, auth)
    assert not check_operations(auth[:1], auth)
    assert not check_operations(auth, auth + [auth[0]])


def test_broker_blocks_evaluator_routes_gets_and_arbitrary_destinations():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'gateway.sock'
        try:
            broker = UnixBroker(path, 1)
        except PermissionError:
            if os.getenv('WHEEL_REQUIRE_BROKER_TEST') == '1': raise
            pytest.skip('Local runtime denies Unix sockets; mandatory in G6 Actions')
        with broker, httpx.Client(transport=httpx.HTTPTransport(uds=str(path)),
                                             base_url='http://broker') as client:
            for route in ('/internal/evaluator/ledger', 'http://example.com/refunds', '/refunds?bypass=1'):
                assert client.post(route, json={}).status_code == 403
            assert client.get('/refunds').status_code == 501
            assert client.post('/refunds', content=b'x' * 8193).status_code == 413


def test_revision_rejects_wrong_checkout_before_any_world():
    with patch.object(g6.subprocess, 'check_output', return_value='other\n'), \
            patch.object(g6.subprocess, 'run'), patch.dict('os.environ', {'GITHUB_SHA': 'expected'}):
        with pytest.raises(IntegrityError): g6.revision()


def test_paid_calls_cannot_start_if_container_probe_fails():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        with patch.object(g6, 'ROOT', root), patch.object(g6, 'revision', return_value='fake'), \
                patch.object(g6, 'variants', return_value=({}, {})), \
                patch.object(g6, 'DockerRuntime') as runtime, patch.object(g6, 'MetaAgent') as agent:
            runtime.return_value.probe.side_effect = RuntimeError('probe failed')
            with pytest.raises(RuntimeError): g6.run()
            agent.assert_not_called()
            assert json.loads((root / 'evidence-g6/run-status.json').read_text())['status'] == 'analysis_error'
            runtime.return_value.close.assert_called_once()


def test_request_budget_is_explicit_and_bounded():
    with pytest.raises(ValueError): MetaAgent(client=object(), max_calls=1000)
    agent = MetaAgent(client=object(), max_calls=52)
    agent.calls = 52
    with pytest.raises(RuntimeError, match='budget'): agent.generate([], False)
