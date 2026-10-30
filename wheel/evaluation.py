"""Frozen C0/C2/C4 comparison over the four reviewed synthetic revision pairs."""
import argparse
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import time

from wheel.evaluation_model import RequestLedger
from wheel.evaluation_protocol import load_protocol, c2_fixed_plans, selection_inputs
from wheel.experiment import ROOT, JAVA, DOMAIN, CLIENT, digest
from wheel.g6 import variants, revision, build_jars, world, source_hashes
from wheel.intake import fixture_commit, inspect, source, git
from wheel.investigator import Investigator, InvestigatorAbstained, InvestigationInconclusive
from wheel.isolation import DockerRuntime
from wheel.meta_agent import MetaAgent
from wheel.plan_guard import PlanGuard, IntegrityError
from wheel.preflight import TriggerNotReached
from wheel.repeatability import POLICY, make_plan, validate_pair, summarize
from wheel.schema_compare import INPUTS, compare

PROTOCOL_SHA = '911e8a5dca874967b52fd313e6f4e975f9813fe8b3f7f2750e0392f6538ef364'


def save(out, name, value):
    (out / name).write_text(json.dumps(value, indent=2, sort_keys=True))


def admitted_sources(protocol):
    """Reconstruct the disclosed commits and require exact pre-registered IDs/bytes."""
    java, python = variants()
    views = {}; provenance = {}; schemas = {}
    for case in protocol['cases']:
        name = case['id']; pin = case['source']; side = case['changed_side']
        text = java[name] if side == 'java' else python[name]
        actual = fixture_commit(ROOT, pin['base_commit'], pin['changed_path'], text, name)
        if actual != pin['candidate_commit']:
            raise IntegrityError('Synthetic source revision differs from protocol')
        item = inspect(ROOT, pin['base_commit'], actual, side)
        if any(item[key] != pin[key] for key in pin):
            raise IntegrityError('Source admission differs from pinned inventory')
        views[name] = {DOMAIN: item['java'], CLIENT: item['python']}
        provenance[name] = {key: value for key, value in item.items() if key not in ('java', 'python')}
        snapshots = {version: {path: source(ROOT, pin[version + '_commit'], path) for path in INPUTS}
                     for version in ('base', 'candidate')}
        schemas[name] = {'source_revisions': {k: pin[k] for k in ('base_commit', 'candidate_commit')},
                         'input_hashes': {v: {p: digest(t.encode()) for p, t in texts.items()}
                                          for v, texts in snapshots.items()},
                         **compare(snapshots['base'], snapshots['candidate'])}
    return java, python, views, provenance, schemas


def implementation_lock(protocol, expected_commit, out):
    actual = revision()
    if actual != expected_commit or len(actual) != 40:
        raise IntegrityError('Implementation revision mismatch')
    paths = sorted(set((ROOT / 'wheel').glob('*.py')) |
                   set((ROOT / JAVA / 'src').rglob('*.*')) |
                   {ROOT / JAVA / 'pom.xml', ROOT / CLIENT,
                    ROOT / 'services/support-agent-python/pyproject.toml',
                    ROOT / 'evaluation/protocol_v1.json', ROOT / '.github/workflows/g7-comparison.yml'})
    hashes = {}
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        if path.is_symlink() or source(ROOT, actual, relative).encode() != path.read_bytes():
            raise IntegrityError('Uncommitted implementation input')
        hashes[relative] = digest(path.read_bytes())
    lock = {'commit': actual, 'protocol_sha256': PROTOCOL_SHA, 'source_hashes': hashes,
            'locked_at': datetime.now(timezone.utc).isoformat(), 'comparison_started': False,
            'planned_caps': protocol['core_budget']}
    save(out, 'implementation-lock.json', lock)
    return actual, paths


def preflight(ledger, out, method, selection, amount, message):
    agent = MetaAgent(client=ledger.scoped(method, 'support', selection), max_calls=7)
    agent.trace_path = out / (selection + '-support-traces.json')
    agent.preflight_path = out / (selection + '-preflight.json')
    # Opaque selection identity is local metadata; prepare's prompt includes no case label.
    agent.scenarios = [{'case': selection, 'amount': amount, 'customer_message': message}]
    seed = agent.prepare()[selection]
    return agent, seed


def select_plans(protocol, views, ledger, out):
    plans = []; selections = []; agents = {}
    for case in protocol['cases']:
        name = case['id']
        fixed = c2_fixed_plans(protocol, name)
        for amount in case['public_fixture']['allowed_amount_minor_units']:
            selection = 'C2-selection-' + str(len(selections) + 1)
            specs = [spec for spec in fixed if spec['amount_minor_units'] == amount]
            entry = {'id': selection, 'method': 'C2', 'case': name, 'amount_minor_units': amount,
                     'status': 'analysis_error', 'proposed_plans': len(specs), 'plans': []}
            selections.append(entry)
            try:
                agent, seed = preflight(ledger, out, 'C2', selection, amount, specs[0]['customer_message'])
                for index, spec in enumerate(specs):
                    proposal = {**spec, 'fault': spec['rule']}
                    plan = make_plan(name, proposal, source_hashes(views[name]), seed, 'fixed')
                    plan['id'] = selection + '-rule-' + str(index + 1)
                    plans.append(plan); agents[plan['id']] = (agent, selection)
                    entry['plans'].append(plan['id'])
                entry['status'] = 'accepted'
            except TriggerNotReached:
                entry['status'] = 'trigger_not_reached'
            except Exception as error:
                entry['error_type'] = type(error).__name__
            save(out, 'selections.json', selections)
    for case in protocol['cases']:
        name = case['id']; selection = 'C4-selection-' + str(len(selections) + 1)
        public = selection_inputs(protocol, name)
        entry = {'id': selection, 'method': 'C4', 'case': name, 'status': 'analysis_error',
                 'proposed_plans': 0, 'plans': []}
        selections.append(entry)
        investigator = Investigator(ledger.scoped('C4', 'investigator', selection),
                                    out / (selection + '-investigator-traces.json'), max_calls=6)
        try:
            changed = DOMAIN if public['changed_side'] == 'java' else CLIENT
            proposal = investigator.investigate(views[name], changed,
                public['public_fixture']['allowed_amount_minor_units'])
            entry.update(proposal=proposal, proposed_plans=2)
            agent, seed = preflight(ledger, out, 'C4', selection,
                                   proposal['amount_minor_units'], proposal['customer_message'])
            for mode in ('selected', 'no_fault'):
                plan = make_plan(name, proposal, source_hashes(views[name]), seed, mode)
                plan['id'] = selection + '-' + mode
                plans.append(plan); agents[plan['id']] = (agent, selection)
                entry['plans'].append(plan['id'])
            entry.update(status='accepted',
                         selected_duplicates_no_fault=proposal['fault']['action'] == 'PASS_THROUGH')
        except InvestigatorAbstained:
            entry['status'] = 'abstained'
        except TriggerNotReached:
            entry['status'] = 'trigger_not_reached'
        except InvestigationInconclusive:
            entry['status'] = 'invalid_plan'
        except Exception as error:
            entry['error_type'] = type(error).__name__
        entry['model_proposal_submissions'] = sum(
            call.get('function', {}).get('name') == 'propose_experiment'
            for trace in getattr(investigator, 'traces', [])
            for call in trace.get('assistant', {}).get('tool_calls', []))
        entry['proposed_plans'] = entry['model_proposal_submissions'] + int('proposal' in entry)
        entry['investigator_requests'] = investigator.calls
        save(out, 'selections.json', selections)
    if sum(p['mode'] == 'fixed' for p in plans) > 18 or len(plans) > 26:
        raise IntegrityError('Frozen plan cap exceeded')
    return plans, selections, agents


def case_status(statuses):
    for status in ('reproduced_regression', 'analysis_error', 'inconclusive',
                   'trigger_not_reached', 'invalid_plan', 'budget_exhausted', 'abstained'):
        if status in statuses:
            return status
    return 'not_reproduced' if statuses else 'not_evaluated'


def case_rows(protocol, schemas, selections, plans, outcomes, records):
    rows = []
    by_id = {p['id']: p for p in plans}
    for case in protocol['case_order']:
        for method in protocol['method_order']:
            if method == 'C0':
                rows.append({'case': case, 'method': method, **schemas[case], 'worlds': 0})
                continue
            chosen = [s for s in selections if s['case'] == case and s['method'] == method]
            ids = [id for s in chosen for id in s['plans']]
            primary = [id for id in ids if by_id[id]['mode'] != 'no_fault']
            statuses = [outcomes[id]['verdict'] for id in primary if id in outcomes]
            statuses += [s['status'] for s in chosen if s['status'] != 'accepted']
            rows.append({'case': case, 'method': method, 'status': case_status(statuses),
                         'primary_plan_ids': primary, 'diagnostic_plan_ids': [id for id in ids if id not in primary],
                         'selection_statuses': [s['status'] for s in chosen],
                         'plan_outcomes': {id: outcomes.get(id, {'verdict': 'not_evaluated'}) for id in ids},
                         'worlds': sum(r['plan_id'] in ids for r in records)})
    return rows


def metrics(protocol, rows, selections, plans, records, attempts):
    result = {}
    for method in protocol['method_order']:
        subset = [r for r in rows if r['method'] == method]
        ids = {p['id'] for p in plans if any(p['id'] in s['plans'] for s in selections if s['method'] == method)}
        worlds = [r for r in records if r['plan_id'] in ids]
        calls = [a for a in attempts if a['method'] == method]
        item = {'case_rows': len(subset), 'worlds_attempted': len(worlds),
                'worlds_completed': sum(r['status'] == 'completed' for r in worlds),
                'request_attempts': len(calls), 'responses_received': sum(a['response_id'] is not None for a in calls),
                'request_errors': sum(a['status'] == 'request_error' for a in calls),
                'usage': [a['usage'] for a in calls], 'valid_plans': len(ids),
                'proposed_plans': sum(s['proposed_plans'] for s in selections if s['method'] == method),
                'runtime_seconds': sum(r.get('runtime_including_continuation_seconds', r.get('runtime_seconds', 0)) for r in worlds),
                'model_proposal_submissions': sum(s.get('model_proposal_submissions', 0) for s in selections if s['method'] == method),
                'baseline_passes': sum(r['world'] == 'base' and r.get('oracle_pass') is True for r in worlds),
                'candidate_failures': sum(r['world'] == 'candidate' and r.get('oracle_pass') is False for r in worlds)}
        if method == 'C0':
            item.update(supported_extractions=sum(r['status'] in ('schema_changed', 'schema_unchanged') for r in subset),
                        schema_flags=sum(r['status'] == 'schema_changed' for r in subset), business_safety_verdict=None)
        else:
            item.update(confirmed_breaking_cases={'numerator': sum(r['status'] == 'reproduced_regression' and
                protocol['evaluator_only_labels'][r['case']] == 'breaking' for r in subset), 'denominator': 2},
                benign_cases_with_confirmed_finding={'numerator': sum(r['status'] == 'reproduced_regression' and
                protocol['evaluator_only_labels'][r['case']] == 'benign' for r in subset), 'denominator': 2},
                cases_runtime_evaluated={'numerator': sum(r['worlds'] > 0 for r in subset), 'denominator': 4},
                case_statuses={status: sum(r['status'] == status for r in subset) for status in
                    ('reproduced_regression', 'not_reproduced', 'inconclusive', 'abstained',
                     'trigger_not_reached', 'invalid_plan', 'budget_exhausted', 'analysis_error')})
        result[method] = item
    return result


def execute_plans(plans, agents, runtime, jars, java, python, out, scratch, guard, manifest):
    records = []; outcomes = {}
    save(out, 'results.json', records); save(out, 'outcomes.json', outcomes)
    for plan in plans:
        rows = []
        for trial in range(3):
            pair = []
            for which in ('base', 'candidate'):
                label = f'{plan["id"]}-{trial}-{which}'
                record = {'label': label, 'plan_id': plan['id'], 'case': plan['case'], 'trial': trial,
                          'world': which, 'oracle_pass': None, 'status': 'analysis_error', 'model_reply': None}
                attempted_at = time.monotonic()
                try:
                    record = world(runtime, plan, trial, which, jars, java, python, out, scratch, guard, manifest)
                    record.update(model_reply=None, continuation='deterministic_no_new_inference')
                    if trial == 0:
                        guard.verify('before_representative_continuation:' + label)
                        agent, selection = agents[plan['id']]
                        if agent.frozen != {selection: plan['seed']}:
                            raise IntegrityError('Tool seed drift')
                        record['continuation'] = 'genuine_Meta'
                        record['model_reply'] = agent.continue_world(selection, record['receipt'])
                except IntegrityError:
                    record.update(status='analysis_error', error_type='IntegrityError')
                    records.append(record); save(out, 'results.json', records)
                    raise
                except Exception as error:
                    record.update(status='analysis_error', error_type=type(error).__name__)
                record['runtime_including_continuation_seconds'] = time.monotonic() - attempted_at
                records.append(record); rows.append(record); pair.append(record)
                save(out, 'results.json', records)
                print(label + ' ' + record['status'], flush=True)
            if all(r['status'] == 'completed' for r in pair):
                validate_pair(*pair, plan, manifest)
        outcomes[plan['id']] = summarize(rows)
        save(out, 'outcomes.json', outcomes)
    return records, outcomes


def run(expected_commit, output):
    # Protocol authorization precedes inference, Docker builds and source execution.
    protocol = load_protocol(ROOT / 'evaluation/protocol_v1.json', PROTOCOL_SHA)
    out = Path(output).absolute(); out.mkdir(exist_ok=False)
    started = time.monotonic(); runtime = None; ledger = None
    commit, paths = implementation_lock(protocol, expected_commit, out)
    guard = PlanGuard(out / 'implementation-lock.json', (out / 'implementation-lock.json').read_bytes(), paths)
    try:
        java, python, views, provenance, schemas = admitted_sources(protocol)
        save(out, 'source-admission.json', provenance); save(out, 'source-snapshots.json', views)
        save(out, 'schema-results.json', schemas)
        # Pop credentials before starting any subprocess/container. SDK construction makes no request.
        agent = MetaAgent(max_calls=1)
        ledger = RequestLedger(agent.client, out / 'request-attempts.json'); ledger.persist()
        with tempfile.TemporaryDirectory(prefix='wheel-comparison-') as directory:
            scratch = Path(directory); runtime = DockerRuntime(ROOT, scratch)
            guard.verify('before_runtime_setup')
            images = runtime.prepare(); probes = runtime.probe()
            jars = build_jars(java, scratch)
            setup_seconds = time.monotonic() - started
            save(out, 'runtime-inputs.json', {'images': images, 'isolation': probes,
                'build_hashes': {name: digest(path.read_bytes()) for name, path in jars.items()}})
            guard.verify('before_selection')
            selected_at = time.monotonic()
            plans, selections, agents = select_plans(protocol, views, ledger, out)
            selection_seconds = time.monotonic() - selected_at
            frozen = {'commit': commit, 'protocol_sha256': PROTOCOL_SHA, 'policy': POLICY,
                      'locked_at': datetime.now(timezone.utc).isoformat(), 'plans': plans,
                      'selections': selections, 'images': images,
                      'build_hashes': {name: digest(path.read_bytes()) for name, path in jars.items()},
                      'selection_attempts_sha256': digest((out / 'request-attempts.json').read_bytes())}
            save(out, 'locked-comparison.json', frozen)
            plan_hash = digest((out / 'locked-comparison.json').read_bytes())
            save(out, 'selection-attempts.json', ledger.attempts)
            for path in jars.values(): guard.bind(path, path.read_bytes())
            for path in out.iterdir():
                if path.name != 'request-attempts.json' and not path.name.endswith('-support-traces.json'):
                    guard.bind(path, path.read_bytes())
            manifest = {'commit': commit, 'plan_hash': plan_hash, 'policy': POLICY, 'images': images,
                        'build_hashes': frozen['build_hashes']}
            guard.verify('all_methods_frozen_before_any_comparative_world')
            ledger.phase = 'worlds'
            execution_started = time.monotonic()
            records, outcomes = execute_plans(plans, agents, runtime, jars, java, python,
                                              out, scratch, guard, manifest)
            if len(records) > 156 or len(ledger.attempts) > 86:
                raise IntegrityError('Core execution cap exceeded')
            guard.verify('before_case_aggregation')
            if revision() != commit:
                raise IntegrityError('Implementation revision changed before aggregation')
            if json.loads((out / 'results.json').read_text()) != records:
                raise IntegrityError('Result evidence drift')
            if json.loads((out / 'request-attempts.json').read_text()) != ledger.attempts:
                raise IntegrityError('Request ledger drift')
            rows = case_rows(protocol, schemas, selections, plans, outcomes, records)
            save(out, 'case-method-results.json', rows)
            for path in out.iterdir(): guard.bind(path, path.read_bytes())
            guard.publish(out / 'summary.json', {'status': 'evaluated', 'commit': commit,
                'protocol_sha256': PROTOCOL_SHA, 'plan_hash': plan_hash, 'case_method_rows': len(rows),
                'metrics': metrics(protocol, rows, selections, plans, records, ledger.attempts),
                'setup_seconds': setup_seconds, 'selection_seconds': selection_seconds,
                'execution_seconds': time.monotonic() - execution_started,
                'wall_seconds': time.monotonic() - started, 'numeric_usd_cost': None,
                'C3': 'not_evaluated', 'withheld_extension': 'not_evaluated',
                'limits': ['four_known_synthetic_cases_not_blind', 'unequal_method_budgets',
                           'deterministic_repeats_not_independent_model_resampling',
                           'trusted_host_and_producer_owned_ledger', 'full_order_refunds_only']})
            save(out, 'evidence-hashes.json', {p.name: digest(p.read_bytes()) for p in out.iterdir() if p.is_file()})
            errors = any(r['status'] == 'analysis_error' for r in rows) or any(r['status'] != 'completed' for r in records)
            save(out, 'run-status.json', {'status': 'completed_with_errors' if errors else 'completed', 'commit': commit})
            if errors:
                raise RuntimeError('Comparison preserved analysis errors')
    except BaseException as error:
        if not (out / 'run-status.json').exists():
            save(out, 'run-status.json', {'status': 'analysis_error', 'error_type': type(error).__name__,
                 'commit': commit, 'wall_seconds': time.monotonic() - started,
                 'request_attempts': len(ledger.attempts) if ledger else 0})
        raise
    finally:
        if runtime: runtime.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-implementation-commit', required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'evidence-comparison')
    args = parser.parse_args()
    try:
        run(args.expected_implementation_commit, args.output)
    except Exception as error:
        print('Comparison stopped: ' + type(error).__name__ + '; inspect preserved evidence.')
        raise SystemExit(1) from None
