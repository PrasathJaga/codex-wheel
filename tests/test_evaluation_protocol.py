"""Offline freeze/fairness guards. These tests do not execute the comparison."""
import copy
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from wheel.evaluation_protocol import ROOT, ACTIONS, CASES, ProtocolError, load_protocol, budget, c2_fixed_plans, selection_inputs

PATH = ROOT / 'evaluation/protocol_v1.json'
EXPECTED = '911e8a5dca874967b52fd313e6f4e975f9813fe8b3f7f2750e0392f6538ef364'  # Independent expected root; never read authorization from the sidecar.


def valid():
    return load_protocol(PATH, EXPECTED)


def write_changed(tmp_path, mutate):
    p = json.loads(PATH.read_text()); mutate(p)
    file = tmp_path / 'protocol.json'; raw = (json.dumps(p, sort_keys=True) + '\n').encode()
    file.write_bytes(raw)
    return file, hashlib.sha256(raw).hexdigest()


def test_core_workload_is_explicit_and_does_not_run_experiments():
    p = valid(); b = budget(p)
    assert b['C2'] == {'plans': 18, 'worlds': 108, 'initial': 6, 'continuations': 36, 'support': 42}
    assert b['C4'] == {'plans': 8, 'worlds': 48, 'initial': 4, 'continuations': 16, 'support': 20, 'investigator': 24}
    assert p['execution_status'] == 'not_run'
    assert p['methods']['C0']['worlds'] == 0
    assert p['methods']['C3']['status'] == 'not_evaluated'


def test_fixed_suite_covers_every_permitted_amount_and_action_without_labels_or_diff():
    p = valid()
    for case in p['cases']:
        suite = c2_fixed_plans(p, case['id'])
        assert {(plan['amount_minor_units'], plan['rule']['action']) for plan in suite} == {
            (amount, action) for amount in case['public_fixture']['allowed_amount_minor_units'] for action in ACTIONS}
        for plan in suite:
            assert plan['rule']['min'] == plan['rule']['max'] == plan['amount_minor_units']
            assert 'USD 25.00' in plan['customer_message'] or 'USD 75.00' in plan['customer_message']
        changed = copy.deepcopy(p)
        changed['evaluator_only_labels'] = {}
        for item in changed['cases']: item['source'] = {'fake_diff': 'must never affect C2 selection'}
        assert c2_fixed_plans(changed, case['id']) == suite


def test_public_context_omits_case_labels_results_and_provenance_and_is_a_copy():
    p = valid()
    for case in CASES:
        exported = selection_inputs(p, case)
        text = json.dumps(exported)
        assert not any(word in text for word in ('evaluator_only', 'breaking', 'benign', 'M1', 'M2', 'B1', 'B2', 'prior_outcomes'))
        exported['public_fixture']['allowed_amount_minor_units'].append(1)
    assert p == valid()


def test_rewriting_sidecar_cannot_reauthorize_a_changed_protocol(tmp_path):
    file, changed_hash = write_changed(tmp_path, lambda p: p['methods']['C2']['actions'].pop())
    file.with_suffix('.sha256').write_text(changed_hash)
    with pytest.raises(ProtocolError, match='hash mismatch'): load_protocol(file, EXPECTED)


@pytest.mark.parametrize('mutate', [
    lambda p: p['methods']['C2']['actions'].pop(),
    lambda p: p['methods']['C2'].update(read_diff=True),
    lambda p: p['methods']['C4'].update(max_initial_investigations_per_case=3),
    lambda p: p['methods']['C4'].update(inherit_stress_plan_on_abstention=True),
    lambda p: p['methods']['C4'].update(use_saved_G6_plans_as_new_selection=True),
    lambda p: p['methods']['C4'].update(fresh_genuine_investigation=False),
    lambda p: p['shared_execution'].update(trials_per_plan=2),
    lambda p: p['shared_execution'].update(reuse_prior_verdicts_as_new_results=True),
    lambda p: p['shared_execution'].update(freeze_all_methods_before_any_comparative_worlds=False),
    lambda p: p['core_budget'].update(max_model_requests=1000),
    lambda p: p['core_budget'].update(numeric_usd_cost=0),
    lambda p: p['budget_fairness'].update(equal_world_or_selection_budget_claim=True),
    lambda p: p['methods']['C3'].update(status='passed'),
    lambda p: p['reporting'].update(abstention_is_verified_safe=True),
    lambda p: p['cases'][0]['source'].update(candidate_commit='a' * 40),
    lambda p: p['source_bundle'].update(artifact_id=1),
    lambda p: p['protected_components'].pop('wheel/verifier.py'),
])
def test_schema_refuses_weakened_baselines_extra_retries_fake_results_and_drift(tmp_path, mutate):
    file, hash = write_changed(tmp_path, mutate)
    # Even a new hash cannot silently make these changes part of v1.
    with pytest.raises(ProtocolError): load_protocol(file, hash)


def test_protected_oracle_edit_rejected_with_same_protocol(tmp_path):
    p = valid()
    for name in p['protected_components']:
        target = tmp_path / name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    (tmp_path / 'wheel/verifier.py').write_text('def check(*a): return True\n')
    with pytest.raises(ProtocolError, match='Protected component changed'):
        load_protocol(PATH, EXPECTED, source_root=tmp_path)
