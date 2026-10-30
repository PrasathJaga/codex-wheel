"""Offline validation/expansion of the frozen evaluation design; never runs a model.

Step 2 must call this guard using a separately trusted expected protocol hash,
then lock the actual evaluator implementation revision before comparisons.
"""
import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path, PurePosixPath
import re

ROOT = Path(__file__).resolve().parents[1]
ACTIONS = ('PASS_THROUGH', 'DROP_DOWNSTREAM_BEFORE_RESPONSE', 'REPLACE_DOWNSTREAM_STATUS_502')
CASES = ('M1', 'M2', 'B1', 'B2')
REQUIRED_PINS = {
    'wheel/g6.py', 'wheel/proxy.py', 'wheel/verifier.py', 'wheel/plan_guard.py', 'wheel/preflight.py',
    'wheel/meta_agent.py', 'wheel/investigator.py', 'wheel/repeatability.py', 'wheel/isolation.py',
    'wheel/wrapper_worker.py', 'wheel/intake.py', 'wheel/replay.py',
    'services/refund-api-java/pom.xml', 'services/support-agent-python/pyproject.toml',
    'services/refund-api-java/src/main/java/dev/codexwheel/refunds/web/RefundController.java',
    'services/refund-api-java/src/main/java/dev/codexwheel/refunds/domain/RefundRequest.java',
    'services/refund-api-java/src/main/java/dev/codexwheel/refunds/domain/RefundEffect.java',
    'docs/REPLAY_EVIDENCE_INDEX.json'}


class ProtocolError(ValueError):
    pass


def require(condition, message):
    if not condition: raise ProtocolError(message)


def c2_fixed_plans(protocol, case_id):
    """Expand the public fixed grid; neither diff nor evaluator labels are read."""
    case = next(c for c in protocol['cases'] if c['id'] == case_id)
    plans = []
    for amount, action in itertools.product(case['public_fixture']['allowed_amount_minor_units'],
                                            protocol['methods']['C2']['actions']):
        amount_usd = f'{amount // 100}.{amount % 100:02d}'
        plans.append({'amount_minor_units': amount,
                      'rule': {'action': action, 'min': amount, 'max': amount},
                      'customer_message': protocol['methods']['C2']['customer_template'].format(amount_usd=amount_usd)})
    return plans


def selection_inputs(protocol, case_id):
    """Only public metadata may be sent to the C4 investigator or support agent."""
    case = next(c for c in protocol['cases'] if c['id'] == case_id)
    return copy.deepcopy({'changed_side': case['changed_side'], 'public_fixture': case['public_fixture'],
                          'source_revisions': {k: case['source'][k] for k in
                              ('base_commit', 'candidate_commit', 'fixed_peer_commit')},
                          'allowed_source_files': protocol['methods']['C4']['allowed_source_files']})


def budget(protocol):
    trials = protocol['shared_execution']['trials_per_plan']
    c2_plans = sum(len(c2_fixed_plans(protocol, case)) for case in CASES)
    c2_initial = sum(len(case['public_fixture']['allowed_amount_minor_units']) for case in protocol['cases'])
    c2_continuations = c2_plans * 2
    c4_plans = len(CASES) * 2  # At most one selected and one separate no-fault plan.
    c4_initial = len(CASES)
    c4_continuations = c4_plans * 2
    return {'C2': {'plans': c2_plans, 'worlds': c2_plans * trials * 2,
                    'initial': c2_initial, 'continuations': c2_continuations,
                    'support': c2_initial + c2_continuations},
            'C4': {'plans': c4_plans, 'worlds': c4_plans * trials * 2,
                    'initial': c4_initial, 'continuations': c4_continuations,
                    'support': c4_initial + c4_continuations,
                    'investigator': len(CASES) * protocol['methods']['C4']['max_turns_per_case']}}


def load_protocol(path, expected_sha256, source_root=ROOT):
    path = Path(path)
    require(not path.is_symlink() and path.is_file(), 'Protocol must be a regular file')
    raw = path.read_bytes()
    require(len(raw) <= 262144, 'Protocol exceeds size bound')
    require(isinstance(expected_sha256, str) and re.fullmatch('[0-9a-f]{64}', expected_sha256) is not None,
            'An independently trusted SHA-256 is required')
    require(hashlib.sha256(raw).hexdigest() == expected_sha256, 'Protocol hash mismatch')
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, 'Duplicate protocol field')
            value[key] = item
        return value
    p = json.loads(raw, object_pairs_hook=unique)
    require(p['schema'] == 'codex-wheel-evaluation-protocol-v1' and p['execution_status'] == 'not_run',
            'Unsupported or outcome-bearing protocol')
    require(p['case_order'] == list(CASES) and p['method_order'] == ['C0', 'C2', 'C4'], 'Case/method inventory drift')
    require([case['id'] for case in p['cases']] == list(CASES), 'Case inventory changed')
    require(p['evaluator_only_labels'] == {'M1': 'breaking', 'M2': 'breaking', 'B1': 'benign', 'B2': 'benign'},
            'Known-case labels changed')
    for case in p['cases']:
        side = 'java' if case['id'] in ('M1', 'B1') else 'python'
        require(case['changed_side'] == side, 'Changed side drift')
        require(case['public_fixture'] == {'order_id': 'ORD-SYN-TRIAL', 'currency': 'USD',
            'refund_scope': 'full_order', 'allowed_amount_minor_units': [2500, 7500] if side == 'java' else [7500]},
            'Public fixture drift')
        source = case['source']
        require(all(re.fullmatch('[0-9a-f]{40}', source[k]) for k in
                    ('base_commit', 'candidate_commit', 'fixed_peer_commit')), 'Unpinned case revision')
        require(source['fixed_peer_commit'] == source['base_commit'], 'Fixed peer revision drift')
        peer = 'python' if side == 'java' else 'java'
        require(source['source_hashes'][peer]['base'] == source['source_hashes'][peer]['candidate'], 'Fixed peer hash drift')
    shared = p['shared_execution']
    require(type(shared['trials_per_plan']) is int and shared['trials_per_plan'] == 3,
            'Exactly three paired trials required')
    require(shared['world_order'] == ['base', 'candidate'] and shared['fresh_state_per_world'] is True and
            shared['fixed_peer_policy_and_oracle'] is True and shared['freeze_before_worlds'] is True and shared['freeze_all_methods_before_any_comparative_worlds'] is True and
            shared['post_outcome_plan_revision'] is False and shared['reuse_prior_verdicts_as_new_results'] is False, 'Execution/freeze policy drift')
    require(shared['representative_continuation_trials'] == [0] and shared['continuation_worlds'] == ['base', 'candidate'],
            'Continuation policy drift')
    c0, c2, c4 = (p['methods'][name] for name in ('C0', 'C2', 'C4'))
    require(c0['new_model_requests'] == c0['worlds'] == 0 and c0['business_safety_claim'] is False,
            'C0 scope expanded')
    require(c2['actions'] == list(ACTIONS) and c2['read_diff'] is False and c2['source_conditioned_selection'] is False,
            'Fixed baseline weakened or made source-conditioned')
    require(c2['customer_template'] == 'Please refund my entire order ORD-SYN-TRIAL for USD {amount_usd}.',
            'Fixed trigger template changed')
    require(c4['max_initial_investigations_per_case'] == c4['max_accepted_selected_plans_per_case'] == 1 and
            c4['max_turns_per_case'] == 6 and c4['max_rejected_proposals_per_case'] == 3 and
            c4['max_tool_calls_per_turn'] == 4, 'Selection/retry budget drift')
    require(c4['tools'] == ['read_diff', 'read_source', 'propose_experiment', 'abstain'] and
            c4['case_labels_or_prior_outcomes_in_model_context'] is False and
            c4['include_no_fault_control'] is True and c4['abstention_runs_worlds'] is False and
            c4['inherit_stress_plan_on_abstention'] is False and c4['failed_trigger_runs_worlds'] is False and c4['fresh_genuine_investigation'] is True and
            c4['use_saved_G6_plans_as_new_selection'] is False,
            'C4 permission/abstention policy drift')
    b = budget(p)
    for name in ('C2', 'C4'):
        method = p['methods'][name]; counts = b[name]
        require(method['max_plans'] == counts['plans'] and method['max_worlds'] == counts['worlds'] and
                method['max_support_initial_requests'] == counts['initial'] and
                method['max_support_continuation_requests'] == counts['continuations'] and
                method['max_support_requests'] == counts['support'], 'Method budget does not match frozen design')
    require(c2['max_investigator_requests'] == 0 and c4['max_investigator_requests'] == b['C4']['investigator'],
            'Investigator budget mismatch')
    model = p['model']
    require(model['provider_base_url'] == 'https://api.meta.ai/v1' and model['id'] == 'muse-spark-1.3' and
            model['investigator'] == {'reasoning_effort': 'low', 'max_completion_tokens': 2048} and
            model['support_agent'] == {'reasoning_effort': 'minimal', 'max_completion_tokens': 1024} and
            model['max_retries'] == 0 and model['request_timeout_seconds'] == 60 and
            model['max_request_message_chars'] == 100000, 'Provider/request policy drift')
    support = b['C2']['support'] + b['C4']['support']; investigator = b['C4']['investigator']
    core = p['core_budget']
    require(core['max_worlds'] == b['C2']['worlds'] + b['C4']['worlds'] == 156 and
            core['max_support_requests'] == support == 62 and core['max_investigator_requests'] == investigator == 24 and
            core['max_model_requests'] == support + investigator == 86 and
            core['max_output_token_capacity'] == support * 1024 + investigator * 2048 == 112640,
            'Core budget mismatch')
    require(core['no_automatic_paid_evaluation_in_this_step'] is True and core['numeric_usd_cost'] is None,
            'Unmeasured costs/execution inserted')
    require(p['budget_fairness']['equal_world_or_selection_budget_claim'] is False and
            p['reporting']['no_dropped_attempts'] is True and p['reporting']['abstention_is_verified_safe'] is False and
            p['reporting']['required_case_method_rows'] == 12 and p['verdicts']['model_prose_is_oracle'] is False,
            'Reporting/verdict policy drift')
    require(p['methods']['C3'] == {'status': 'not_evaluated', 'required': False} and
            p['withheld_extension']['status'] == 'not_evaluated' and
            p['withheld_extension']['included_in_core_budget'] is False, 'Unperformed work relabeled')
    require(set(p['protected_components']) == REQUIRED_PINS, 'Missing or unexpected protected component pins')
    for name, sha in p['protected_components'].items():
        relative = PurePosixPath(name)
        require(not relative.is_absolute() and '..' not in relative.parts and '\\' not in name,
                'Unsafe protected path')
        target = Path(source_root)
        for part in relative.parts:
            target = target / part
            require(not target.is_symlink(), 'Protected symlink')
        require(target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == sha,
                'Protected component changed: ' + name)
    evidence = json.loads((Path(source_root) / 'docs/REPLAY_EVIDENCE_INDEX.json').read_text())
    require(p['source_bundle'] == {'workflow_run': evidence['workflow_run'], 'artifact_id': evidence['bundle_artifact'],
                                  'manifest_sha256': evidence['manifest_sha256'], 'zip_sha256': evidence['bundle_zip_sha256']},
            'Source bundle provenance drift')
    for case in p['cases']:
        prior = evidence['source_pairs'][case['id']]
        require(case['source'] == {k: prior[k] for k in
                    ('base_commit', 'candidate_commit', 'fixed_peer_commit', 'changed_path', 'source_hashes')},
                'Pinned source inventory disagrees with inspected evidence')
    return p


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    args = parser.parse_args()
    try:
        protocol = load_protocol(args.protocol, args.expected_sha256)
        print(json.dumps({'status': 'protocol_verified', 'comparison_executed': False,
                          'case_method_rows': 12, 'planned_budget_caps': budget(protocol)}, sort_keys=True))
    except Exception as error:
        print(json.dumps({'status': 'protocol_rejected', 'error_type': type(error).__name__}))
        raise SystemExit(1) from None
