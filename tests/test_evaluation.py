"""Comparison boundaries: real schema extraction, budgets, abstentions and repeats."""
import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from wheel import evaluation as evaluation
from wheel.evaluation_model import RequestLedger, RequestLimit
from wheel.evaluation_protocol import ROOT, load_protocol
from wheel.investigator import InvestigatorAbstained
from wheel.meta_agent import MetaAgent, MODEL, TOOL, fingerprint
from wheel.plan_guard import IntegrityError, PlanGuard
from wheel.preflight import TriggerNotReached
from wheel.schema_compare import INPUTS, CONTROLLER, META, REQUEST, compare, extract


def protocol():
    return load_protocol(ROOT / 'evaluation/protocol_v1.json', evaluation.PROTOCOL_SHA)


def source_inputs():
    return {p: (ROOT / p).read_text() for p in INPUTS}


def test_exact_commit_admission_and_extracted_surface():
    p = protocol()
    _, _, views, provenance, schemas = evaluation.admitted_sources(p)
    assert len(views) == len(provenance) == len(schemas) == 4
    assert all(s['status'] == 'schema_unchanged' for s in schemas.values())
    for case in p['cases']:
        assert provenance[case['id']]['candidate_commit'] == case['source']['candidate_commit']
    surface = extract(source_inputs())
    assert surface['http']['path'] == '/refunds'
    assert surface['http']['request']['amount_minor_units'] == 'integer'
    assert surface['http']['response']['committed_minor_units'] == {'type': 'integer'}
    assert surface['tool']['parameters'] == TOOL['function']['parameters']


@pytest.mark.parametrize('path,before,after', [
    (CONTROLLER, '@PostMapping("/refunds")', '@PostMapping("/refunds-v2")'),
    (CONTROLLER, '@RequestHeader("Idempotency-Key")', '@RequestHeader("Idempotency-Key-v2")'),
    (CONTROLLER, '@JsonProperty("currency") String', '@JsonProperty("currency_code") String'),
    (CONTROLLER, '"committed_minor_units",effect.amountMinorUnits()', '"committed_minor_units",effect.orderId()'),
    (CONTROLLER, '"status","committed"', '"status","pending"'),
    (REQUEST, 'long amountMinorUnits', 'String amountMinorUnits'),
    (META, "'name': 'issue_refund'", "'name': 'issue_refund_v2'"),
    (META, "'enum': ['USD']", "'enum': ['USD', 'EUR']"),
])
def test_schema_comparator_detects_actual_contract_changes(path, before, after):
    base = source_inputs(); candidate = copy.deepcopy(base)
    assert before in candidate[path]
    candidate[path] = candidate[path].replace(before, after)
    result = compare(base, candidate)
    assert result['status'] == 'schema_changed'
    assert result['business_safety_verdict'] is None


@pytest.mark.parametrize('path,before,after', [
    (CONTROLLER, 'return Map.of("refund_effect_id"', 'return dynamicMap("refund_effect_id"'),
    (CONTROLLER, 'long amountMinorUnits,', 'double amountMinorUnits,'),
    (META, 'TOOL = {', 'TOOL = dict(**{'),
])
def test_unsupported_extraction_is_never_a_pass(path, before, after):
    base = source_inputs(); candidate = copy.deepcopy(base)
    candidate[path] = candidate[path].replace(before, after)
    assert compare(base, candidate)['status'] == 'unsupported'


def test_pinned_source_mismatch_prevents_admission(monkeypatch):
    monkeypatch.setattr(evaluation, 'fixture_commit', lambda *args: 'a' * 40)
    with pytest.raises(IntegrityError):
        evaluation.admitted_sources(protocol())


def request(role='support', text='public prompt'):
    return {'model': MODEL, 'messages': [{'role': 'user', 'content': text}],
            'tools': [TOOL], 'tool_choice': 'auto',
            'max_completion_tokens': 2048 if role == 'investigator' else 1024,
            'reasoning_effort': 'low' if role == 'investigator' else 'minimal'}


def failed_client():
    class ProviderFailure(Exception):
        status_code = 503
    client = Mock()
    client.chat.completions.create.side_effect = ProviderFailure('sensitive body must not be persisted')
    return client


def test_failed_requests_count_toward_budget_without_persisting_exception_bodies(tmp_path):
    client = failed_client(); ledger = RequestLedger(client, tmp_path / 'attempts.json')
    scoped = ledger.scoped('C4', 'investigator', 'opaque-selection')
    for _ in range(6):
        with pytest.raises(Exception): scoped.chat.completions.create(**request('investigator'))
    with pytest.raises(RequestLimit): scoped.chat.completions.create(**request('investigator'))
    assert client.chat.completions.create.call_count == 6
    assert len(ledger.attempts) == 6
    assert all(a['status'] == 'request_error' and a['http_status'] == 503 for a in ledger.attempts)
    assert 'sensitive body' not in ledger.path.read_text()
    ledger.phase = 'worlds'
    with pytest.raises(RequestLimit):
        ledger.scoped('C4', 'investigator', 'new-selection').chat.completions.create(**request('investigator'))
    assert client.chat.completions.create.call_count == 6


def test_preflight_has_one_attempt_and_oversized_prompts_never_reach_provider(tmp_path):
    client = failed_client(); ledger = RequestLedger(client, tmp_path / 'attempts.json')
    scoped = ledger.scoped('C2', 'support', 'opaque-selection')
    with pytest.raises(RequestLimit): scoped.chat.completions.create(**request(text='x' * 100001))
    assert not ledger.attempts
    with pytest.raises(Exception): scoped.chat.completions.create(**request())
    with pytest.raises(RequestLimit): scoped.chat.completions.create(**request())
    assert len(ledger.attempts) == client.chat.completions.create.call_count == 1


@pytest.mark.parametrize('method,role,cap', [('C2', 'support', 42), ('C4', 'support', 20), ('C4', 'investigator', 24)])
def test_method_caps_include_all_failures(tmp_path, method, role, cap):
    client = failed_client(); ledger = RequestLedger(client, tmp_path / 'attempts.json')
    for i in range(cap):
        with pytest.raises(Exception):
            ledger.scoped(method, role, str(i)).chat.completions.create(**request(role))
    with pytest.raises(RequestLimit):
        ledger.scoped(method, role, 'extra').chat.completions.create(**request(role))
    assert client.chat.completions.create.call_count == cap


def fake_selection(monkeypatch, tmp_path, failed_amount=None):
    calls = []
    def preflight(ledger, out, method, selection, amount, message):
        calls.append((method, amount, message))
        if failed_amount and method == 'C2' and amount == failed_amount:
            raise TriggerNotReached()
        args = {'order_id': 'ORD-SYN-TRIAL', 'amount_minor_units': amount,
                'currency': 'USD', 'refund_scope': 'full_order'}
        payload = {'arguments': args}
        seed = {'payload': payload, 'sha256': fingerprint(payload)}
        agent = SimpleNamespace(frozen={selection: seed}, continue_world=Mock(return_value={'content': 'synthetic test reply'}))
        return agent, seed
    class Investigator:
        count = 0
        def __init__(self, *args, **kwargs): self.calls = 0
        def investigate(self, sources, path, amounts):
            Investigator.count += 1; self.calls = 1
            if Investigator.count > 2: raise InvestigatorAbstained()
            return {'amount_minor_units': amounts[0], 'customer_message': 'Synthetic customer request',
                    'fault': {'action': 'DROP_DOWNSTREAM_BEFORE_RESPONSE', 'min': amounts[0], 'max': amounts[0]}}
    monkeypatch.setattr(evaluation, 'preflight', preflight)
    monkeypatch.setattr(evaluation, 'Investigator', Investigator)
    p = protocol(); _, _, views, _, _ = evaluation.admitted_sources(p)
    ledger = SimpleNamespace(scoped=lambda *args: None)
    result = evaluation.select_plans(p, views, ledger, tmp_path)
    return p, result, calls


def test_complete_fixed_grid_and_abstention_without_inherited_controls(monkeypatch, tmp_path):
    _, (plans, selections, agents), calls = fake_selection(monkeypatch, tmp_path)
    assert len(plans) == 22
    assert sum(p['mode'] == 'fixed' for p in plans) == 18
    assert sum(p['mode'] == 'selected' for p in plans) == 2
    assert sum(p['mode'] == 'no_fault' for p in plans) == 2
    assert [s['status'] for s in selections if s['method'] == 'C4'] == ['accepted', 'accepted', 'abstained', 'abstained']
    assert not [p for p in plans if p['case'] in ('B1', 'B2') and p['mode'] != 'fixed']
    assert len([c for c in calls if c[0] == 'C2']) == 6
    for s in selections:
        seeds = [p['seed'] for p in plans if p['id'] in s['plans']]
        assert not seeds or all(seed == seeds[0] for seed in seeds)


def test_failed_amount_has_no_world_plans_and_does_not_replan(monkeypatch, tmp_path):
    _, (plans, selections, _), calls = fake_selection(monkeypatch, tmp_path, failed_amount=2500)
    assert sum(p['mode'] == 'fixed' for p in plans) == 12
    failures = [s for s in selections if s['status'] == 'trigger_not_reached']
    assert len(failures) == 2
    assert all(s['plans'] == [] and s['proposed_plans'] == 3 for s in failures)
    assert len([c for c in calls if c[0] == 'C2']) == 6


def test_only_trial_zero_has_fresh_continuations_and_all_other_replies_are_null(monkeypatch, tmp_path):
    _, (plans, selections, agents), _ = fake_selection(monkeypatch, tmp_path)
    def world(runtime, plan, trial, which, *args):
        return {'plan_id': plan['id'], 'case': plan['case'], 'trial': trial, 'world': which,
                'status': 'completed', 'oracle_pass': True, 'events': [{'key_sha256': 'fixed', 'action': plan['rule']['action']}],
                'effects': [{'amount_minor_units': plan['fixture']['amount_minor_units']}], 'transport_errors': [],
                'receipt': {'status': 'committed'}}
    monkeypatch.setattr(evaluation, 'world', world)
    parity = Mock(); monkeypatch.setattr(evaluation, 'validate_pair', parity)
    lock = tmp_path / 'lock'; lock.write_text('frozen')
    guard = PlanGuard(lock, b'frozen', [])
    records, outcomes = evaluation.execute_plans(plans, agents, None, {}, {}, {}, tmp_path, tmp_path, guard, {})
    assert len(records) == 132
    assert parity.call_count == 66
    assert sum(r['model_reply'] is not None for r in records) == 44
    assert all(r['model_reply'] is None for r in records if r['trial'] in (1, 2))
    assert all(o['verdict'] == 'not_reproduced' for o in outcomes.values())


def test_case_aggregation_retains_errors_and_diagnostic_findings_do_not_become_primary():
    p = protocol()
    schemas = {case: {'status': 'schema_unchanged'} for case in p['case_order']}
    selections = [{'id': 's1', 'method': 'C4', 'case': 'M1', 'status': 'accepted', 'plans': ['a', 'b']},
                  {'id': 's2', 'method': 'C2', 'case': 'M1', 'status': 'trigger_not_reached', 'plans': []}]
    plans = [{'id': 'a', 'mode': 'selected'}, {'id': 'b', 'mode': 'no_fault'}]
    outcomes = {'a': {'verdict': 'inconclusive'}, 'b': {'verdict': 'reproduced_regression'}}
    rows = evaluation.case_rows(p, schemas, selections, plans, outcomes, [])
    assert len(rows) == 12
    assert next(r for r in rows if r['case'] == 'M1' and r['method'] == 'C4')['status'] == 'inconclusive'
    assert next(r for r in rows if r['case'] == 'M1' and r['method'] == 'C2')['status'] == 'trigger_not_reached'
    assert evaluation.case_status(['not_reproduced', 'analysis_error']) == 'analysis_error'
    assert evaluation.case_status(['analysis_error', 'reproduced_regression']) == 'reproduced_regression'
    assert evaluation.case_status(['abstained']) == 'abstained'


def test_full_orchestration_freezes_all_selections_before_worlds(monkeypatch, tmp_path):
    p, selected, calls = fake_selection(monkeypatch, tmp_path)
    plans, selections, agents = selected
    calls.clear()
    def selected_once(*args):
        calls.append('all_selections_frozen')
        return plans, selections, agents
    monkeypatch.setattr(evaluation, 'select_plans', selected_once)
    def lock(protocol, expected, out):
        evaluation.save(out, 'implementation-lock.json', {'commit': expected})
        return expected, []
    monkeypatch.setattr(evaluation, 'implementation_lock', lock)
    monkeypatch.setattr(evaluation, 'MetaAgent', lambda **kw: SimpleNamespace(client=Mock()))
    class Runtime:
        def __init__(self, *args): self.closed = False
        def prepare(self): return {}
        def probe(self): return {}
        def close(self): self.closed = True
    monkeypatch.setattr(evaluation, 'DockerRuntime', Runtime)
    jar = tmp_path / 'base.jar'; jar.write_bytes(b'test jar')
    monkeypatch.setattr(evaluation, 'build_jars', lambda *args: {'base': jar})
    def world(runtime, plan, trial, which, *args):
        assert calls == ['all_selections_frozen']
        return {'plan_id': plan['id'], 'case': plan['case'], 'trial': trial, 'world': which,
                'status': 'completed', 'oracle_pass': True, 'events': [{'key_sha256': 'fixed', 'action': plan['rule']['action']}],
                'effects': [{'amount_minor_units': plan['fixture']['amount_minor_units']}], 'transport_errors': [],
                'receipt': {'status': 'committed'}}
    monkeypatch.setattr(evaluation, 'world', world)
    monkeypatch.setattr(evaluation, 'validate_pair', lambda *args: None)
    out = tmp_path / 'output'
    evaluation.run('a' * 40, out)
    summary = json.loads((out / 'summary.json').read_text())
    assert summary['case_method_rows'] == 12
    assert summary['metrics']['C2']['worlds_completed'] == 108
    assert summary['metrics']['C4']['worlds_completed'] == 24
    assert summary['metrics']['C4']['case_statuses']['abstained'] == 2
    assert summary['numeric_usd_cost'] is None
    assert json.loads((out / 'run-status.json').read_text())['status'] == 'completed'
