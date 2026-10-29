"""Protected G6 aggregation. Labels and model prose never determine a verdict."""
import copy
from wheel.plan_guard import IntegrityError
from wheel.meta_agent import fingerprint

TRIALS = 3
POLICY = 'g6-three-pairs-v1'


def validate_pair(base, candidate, plan, manifest):
    """Enforce actual peer, fixture, policy, image, seed and intervention parity."""
    for record in (base, candidate):
        for key in ('plan_hash', 'fixture_sha256', 'seed_sha256', 'rule_sha256',
                    'policy', 'images'):
            expected = manifest[key] if key in manifest else fingerprint(plan[key.removesuffix('_sha256')])
            if record[key] != expected:
                raise IntegrityError('World parity mismatch: ' + key)
        if record['reset_empty'] is not True or record['restart_recovered'] is not True:
            raise IntegrityError('World reset/recovery failed')
    if base['world'] != 'base' or candidate['world'] != 'candidate' or base['trial'] != candidate['trial']:
        raise IntegrityError('World pairing mismatch')
    for side in ('java', 'python'):
        expected_base = plan['source_hashes'][side]['base']
        expected_candidate = plan['source_hashes'][side]['candidate']
        if base[side + '_sha256'] != expected_base or candidate[side + '_sha256'] != expected_candidate:
            raise IntegrityError('Wrong source variant: ' + side)
    for record in (base, candidate):
        variant = plan['case'] if record['world'] == 'candidate' and plan['changed_side'] == 'java' else 'base'
        if record['jar_sha256'] != manifest['build_hashes'][variant]:
            raise IntegrityError('Wrong compiled Java artifact')
    peer = 'python' if plan['changed_side'] == 'java' else 'java'
    if base[peer + '_sha256'] != candidate[peer + '_sha256']:
        raise IntegrityError('Unchanged peer drift')


def signature(record):
    """Relevant causal signature excludes generated IDs/timestamps/model wording."""
    keys = [event['key_sha256'] for event in record['events']]
    return (record['oracle_pass'], len(record['effects']),
            sum(row['amount_minor_units'] for row in record['effects']),
            len(keys), len(set(keys)), tuple(e['action'] for e in record['events']),
            tuple(record['transport_errors']))


def summarize(records, trials=TRIALS):
    if type(trials) is not int or trials < 3:
        raise ValueError('At least three paired trials required')
    paired = []
    for trial in range(trials):
        rows = [r for r in records if r['trial'] == trial]
        base = [r for r in rows if r['world'] == 'base']
        candidate = [r for r in rows if r['world'] == 'candidate']
        if len(base) != 1 or len(candidate) != 1:
            return {'verdict': 'inconclusive', 'reason': 'missing_or_duplicate_world', 'pairs': paired}
        b, c = base[0], candidate[0]
        paired.append({'trial': trial, 'baseline_pass': b.get('oracle_pass'),
                       'candidate_pass': c.get('oracle_pass'),
                       'baseline_status': b['status'], 'candidate_status': c['status']})
    if len(records) != 2 * trials:
        return {'verdict': 'inconclusive', 'reason': 'unexpected_worlds', 'pairs': paired}
    if any(r['status'] != 'completed' for r in records):
        verdict, reason = 'analysis_error', 'world_or_continuation_failed'
    elif any(not p['baseline_pass'] for p in paired):
        verdict, reason = 'inconclusive', 'baseline_invariant_failed'
    else:
        candidate_passes = sum(p['candidate_pass'] for p in paired)
        stable = all(len({signature(r) for r in records if r['world'] == world}) == 1
                     for world in ('base', 'candidate'))
        if not stable or candidate_passes not in (0, trials):
            verdict, reason = 'inconclusive', 'mixed_behavioral_signatures'
        elif candidate_passes == trials:
            verdict, reason = 'not_reproduced', 'no_violation_under_tested_conditions'
        else:
            verdict, reason = 'reproduced_regression', 'repeatable_baseline_pass_candidate_fail'
    return {'verdict': verdict, 'reason': reason, 'pairs': paired,
            'baseline_passes': sum(p['baseline_pass'] is True for p in paired),
            'candidate_passes': sum(p['candidate_pass'] is True for p in paired),
            'paired_trials': trials}


def make_plan(case, proposal, sources, seed, mode='selected'):
    side = 'java' if case in ('M1', 'B1') else 'python'
    rule = copy.deepcopy(proposal['fault'])
    if mode == 'no_fault': rule['action'] = 'PASS_THROUGH'
    fixture = {'order_id': 'ORD-SYN-TRIAL', 'amount_minor_units': proposal['amount_minor_units']}
    return {'id': case + '-' + mode, 'case': case, 'mode': mode, 'changed_side': side,
            'rule': rule, 'fixture': fixture, 'seed': copy.deepcopy(seed),
            'source_hashes': sources}
