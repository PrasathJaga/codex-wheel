"""Synthetic counterfactuals: manual matrix or bounded live Meta support-agent slice."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time
import sys

import httpx
from wheel.proxy import Gateway
from wheel.verifier import check
from wheel.plan_guard import PlanGuard, IntegrityError

ROOT = Path(__file__).resolve().parents[1]
JAVA = 'services/refund-api-java'
CLIENT = 'services/support-agent-python/refund_tool/client.py'
DOMAIN = JAVA + '/src/main/java/dev/codexwheel/refunds/domain/RefundService.java'

def digest(data): return hashlib.sha256(data).hexdigest()
def port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0)); return s.getsockname()[1]

def child_env():
    """Allow only runtime plumbing into candidate subprocesses."""
    return {k:v for k,v in os.environ.items() if k in
            {"PATH", "JAVA_HOME", "HOME", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT"}}

def start(jar, ledger, token, log):
    p = port()
    process = subprocess.Popen(['java', '-jar', str(jar), '--server.port='+str(p)],
        env={**child_env(), 'WHEEL_LEDGER_PATH':str(ledger), 'WHEEL_EVALUATOR_TOKEN':token}, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(100):
        try:
            if httpx.get(f'http://127.0.0.1:{p}/health', timeout=.5, trust_env=False).status_code == 200:
                return process, p
        except httpx.TransportError: pass
        if process.poll() is not None: raise RuntimeError('Java exited; inspect artifact log')
        time.sleep(.2)
    process.terminate(); process.wait(timeout=10)
    raise RuntimeError('readiness timeout')

def stop(process):
    process.terminate()
    try: process.wait(timeout=10)
    except subprocess.TimeoutExpired: process.kill(); process.wait()

def snapshot(p, token):
    with httpx.Client(base_url=f'http://127.0.0.1:{p}', trust_env=False) as c:
        assert c.get('/internal/evaluator/ledger').status_code == 403
        r = c.get('/internal/evaluator/ledger',headers={'X-Evaluator-Token':token})
        r.raise_for_status(); return r.json()['effects']

def run(agent=None, investigate=False):
    out = ROOT/('evidence-g5' if investigate else 'evidence-g4' if agent else 'evidence'); out.mkdir(exist_ok=True)
    # Refuse to reuse an output directory that could contain an old success summary.
    if any(out.iterdir()): raise RuntimeError('Evidence directory must be empty')
    base_source = (ROOT/DOMAIN).read_text()
    client_source = (ROOT/CLIENT).read_text()
    needle = 'if (prior != null) {'
    assert base_source.count(needle) == 1
    candidate = base_source.replace(needle, 'if (prior != null && request.amountMinorUnits() > 2500) {')
    m2needle = 'if response.status_code==502:\n                if attempt<max_attempts:\n                    continue'
    assert client_source.count(m2needle) == 1
    m2 = client_source.replace(m2needle, 'if response.status_code==502:\n                if attempt<max_attempts:\n                    key = str(uuid.uuid4())\n                    continue')
    # Actual benign source changes; not switches that silently reuse identical bytes.
    variants = {'base':base_source, 'M1':candidate, 'B1':base_source.replace('var prior =', 'final var prior =')}
    wrappers = {'base':client_source, 'M2':m2, 'B2':client_source.replace('last_exception: Exception | None = None', 'last_exception: Exception | None = None  # benign annotation')}
    plans = []
    for case, amount, action in [('M1',2500,'DROP_DOWNSTREAM_BEFORE_RESPONSE'), ('M2',7500,'REPLACE_DOWNSTREAM_STATUS_502'), ('B1',2500,'DROP_DOWNSTREAM_BEFORE_RESPONSE'), ('B2',7500,'REPLACE_DOWNSTREAM_STATUS_502')]:
        for fault in [False, True]:
            plans.append(dict(case=case, amount=amount, action=action if fault else 'PASS_THROUGH'))
    investigator = None
    proposals = None
    if investigate:
        if agent is None: raise RuntimeError('G5 requires a genuine support-agent gateway')
        from wheel.investigator import Investigator
        investigator=Investigator(agent.client, out/'investigator-traces.json')
        proposals={};source_snapshots={};selected=[];scenarios=[]
        for case, changed_path in [('M1',DOMAIN),('M2',CLIENT)]:
            sources={DOMAIN:{'base':base_source,'candidate':variants['M1'] if case=='M1' else base_source},
                     CLIENT:{'base':client_source,'candidate':wrappers['M2'] if case=='M2' else client_source}}
            source_snapshots[case]=sources
            # v3.2 requires the Python-change case to use a high-value fixture.
            # This is public eligibility, not an outcome-dependent change.
            allowed_amounts=(2500,7500) if case=='M1' else (7500,)
            proposal=investigator.investigate(sources, changed_path, allowed_amounts)
            proposals[case]=proposal
            selected.append(dict(case=case,amount=proposal['amount_minor_units'],
                action=proposal['fault']['action'],min=proposal['fault']['min'],max=proposal['fault']['max']))
            scenarios.append(dict(case=case,amount=proposal['amount_minor_units'],customer_message=proposal['customer_message']))
        (out/'investigator-proposals.json').write_text(json.dumps(proposals,indent=2))
        (out/'source-snapshots.json').write_text(json.dumps(source_snapshots,indent=2))
        plans=selected;agent.scenarios=scenarios
    trials = 1 if agent else 3
    if agent and not investigate: plans = [p for p in plans if p['case'] in ['M1','M2'] and p['action'] != 'PASS_THROUGH']
    if agent:
        agent.trace_path = out/'model-traces.json'
        agent.preflight_path = out/'preflight.json'
    model_intents = agent.prepare() if agent else None
    source_paths = sorted(set(list((ROOT/'wheel').glob('*.py')) +
        list((ROOT/JAVA/'src').rglob('*.java')) + list((ROOT/JAVA/'src').rglob('*.properties')) +
        [ROOT/JAVA/'pom.xml', ROOT/CLIENT, ROOT/'services/support-agent-python/pyproject.toml']))
    source_hashes = {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in source_paths}
    frozen = json.dumps({'plans':plans, 'java':{k:digest(v.encode()) for k,v in variants.items()},
        'python':{k:digest(v.encode()) for k,v in wrappers.items()},
        'oracle_sha256':digest((ROOT/'wheel/verifier.py').read_bytes()),
        'proxy_sha256':digest((ROOT/'wheel/proxy.py').read_bytes()),
        'commit':os.getenv('GITHUB_SHA','local'), 'policy_version':'preflight-freeze-v1',
        'investigator_policy_version':'source-tools-high-value-v2' if investigate else None,
        'investigator_proposals':proposals, 'sources':source_hashes, 'preflight_sha256':digest((out/'preflight.json').read_bytes()) if agent else None, 'trials':trials, 'model_intents':model_intents},sort_keys=True).encode()
    (out/'frozen-plan.json').write_bytes(frozen)
    plan_hash=digest(frozen)
    (out/'locked_experiment.json').write_bytes(frozen)
    (out/'locked_experiment.sha256').write_text(plan_hash+'\n')
    (out/'tool_intent_seed.json').write_text(json.dumps(model_intents,sort_keys=True))
    guard=PlanGuard(out/'frozen-plan.json', frozen, source_paths)
    for path in [out/'locked_experiment.json', out/'locked_experiment.sha256', out/'tool_intent_seed.json']:
        guard.bind(path, path.read_bytes())
    if agent: guard.bind(out/'preflight.json', (out/'preflight.json').read_bytes())
    if investigate:
        for name in ['investigator-traces.json','investigator-proposals.json','source-snapshots.json']:
            guard.bind(out/name, (out/name).read_bytes())
    guard.verify('before_build')
    results=[]
    try:
        with tempfile.TemporaryDirectory() as td:
            td=Path(td); jars={}
            for name, source in variants.items():
                (ROOT/DOMAIN).write_text(source)
                subprocess.run(['mvn','-B','-f',str(ROOT/JAVA/'pom.xml'), 'clean','package','-DskipTests'], check=True, env=child_env())
                jar=td/(name+'.jar'); jar.write_bytes((ROOT/JAVA/'target/refund-api-java-0.1.0-SNAPSHOT.jar').read_bytes()); jars[name]=jar
                (out/(name+'.java')).write_text(source)
            (ROOT/DOMAIN).write_text(base_source)
            for name, source in wrappers.items(): (out/(name+'-client.py')).write_text(source)
            for name, jar in jars.items(): guard.bind(jar, jar.read_bytes())
            for name in variants: guard.bind(out/(name+'.java'), variants[name].encode())
            for name in wrappers: guard.bind(out/(name+'-client.py'), wrappers[name].encode())
            (out/'build-hashes.json').write_text(json.dumps({k:digest(p.read_bytes()) for k,p in jars.items()},sort_keys=True))
            guard.bind(out/'build-hashes.json', (out/'build-hashes.json').read_bytes())
            for plan in plans:
                for trial in range(trials):
                    pair=[]
                    for world in ['base','candidate']:
                        case=plan['case']; label=f'{case}-{plan["action"]}-{trial}-{world}'
                        java_variant=case if world=='candidate' and case in variants else 'base'
                        py_variant=case if world=='candidate' and case in wrappers else 'base'
                        module_file=td/(py_variant+'.py'); module_file.write_text(wrappers[py_variant])
                        guard.bind(module_file, wrappers[py_variant].encode())
                        if agent and agent.frozen != model_intents:
                            raise IntegrityError('In-memory tool intent differs from locked plan')
                        ledger=td/(label+'.tsv'); token=secrets.token_hex(32)
                        authorization={'order_id':'ORD-SYN-TRIAL','amount_minor_units':plan['amount']}
                        rule={'action':plan['action'],'min':plan.get('min',plan['amount']),'max':plan.get('max',plan['amount'])}
                        with (out/(label+'.log')).open('w') as log:
                            process,p=guard.call('before_start:'+label, start,jars[java_variant],ledger,token,log)
                            try:
                                assert snapshot(p, token)==[]
                                def observe_commit(upstream):
                                    rows=ledger.read_text().splitlines()
                                    assert any(row.split('\t')[0]==upstream['refund_effect_id'] for row in rows)
                                    return {'effect_id':upstream['refund_effect_id'], 'ledger_sha256':digest(ledger.read_bytes()),'rows_before_downstream_action':len(rows)}
                                with Gateway(p,rule,observe_commit) as gateway:
                                    arguments = agent.intent(case)['arguments'] if agent else authorization
                                    worker = guard.call('before_wrapper:'+label, subprocess.run,[sys.executable, '-m', 'wheel.wrapper_worker',
                                        str(module_file), f'http://127.0.0.1:{gateway.port}'],
                                        input=json.dumps(arguments), text=True, capture_output=True,
                                        timeout=30, env=child_env(), check=True)
                                    outcome = json.loads(worker.stdout)
                                    receipt=outcome['receipt']; transport_errors=outcome['transport_errors']
                                    events=list(gateway.events)
                                assert bool(transport_errors)==(plan['action']=='DROP_DOWNSTREAM_BEFORE_RESPONSE')
                                effects=snapshot(p,token)
                                disk_rows=[line.split('\t') for line in ledger.read_text().splitlines()]
                                assert len(disk_rows)==len(effects)
                                for row,effect in zip(disk_rows,effects):
                                    assert row[:6]==[effect['effect_id'],effect['order_id'],str(effect['amount_minor_units']),effect['currency'],effect['refund_scope'],effect['idempotency_key_sha256']]
                                (out/(label+'.tsv')).write_bytes(ledger.read_bytes())
                                assert len(events)==(1 if plan['action']=='PASS_THROUGH' else 2)
                                assert all(e['upstream_status']==200 for e in events)
                                assert events[0]['upstream_body']['refund_effect_id']==effects[0]['effect_id']
                                assert events[0]['action']==plan['action']
                                keys=[e['key_sha256'] for e in events]
                                expected_change=world=='candidate' and case=='M2' and plan['action']=='REPLACE_DOWNSTREAM_STATUS_502'
                                assert (len(set(keys))==2)==expected_change
                            finally: stop(process)
                            # Restart checks persisted effects and stable-key dedup recovery.
                            process,p=guard.call('before_start:'+label, start,jars[java_variant],ledger,token,log)
                            try: assert snapshot(p,token)==effects
                            finally: stop(process)
                        guard.verify('before_continuation:'+label)
                        model_reply = agent.continue_world(case, receipt) if agent else None
                        if agent: (out/'model-traces.json').write_text(json.dumps(agent.traces,indent=2))
                        valid=check(effects,authorization)
                        record=dict(label=label, case=case,world=world,trial=trial,plan_hash=plan_hash,
                            model_reply=model_reply,transport_errors=transport_errors,oracle_pass=valid,effects=effects,events=events,receipt=receipt,
                            restart_recovered=True,java_sha256=digest(variants[java_variant].encode()),
                            python_sha256=digest(wrappers[py_variant].encode()))
                        results.append(record);pair.append(valid)
                        (out/'results.json').write_text(json.dumps(results,indent=2))
                    expected_regression=plan['case'] in ['M1','M2'] and plan['action']!='PASS_THROUGH'
                    if not investigate: assert pair==[True,not expected_regression], (plan,pair)
            assert digest((out/'frozen-plan.json').read_bytes())==plan_hash
            assert digest((ROOT/'wheel/proxy.py').read_bytes())==json.loads(frozen)['proxy_sha256']
            assert digest((ROOT/'wheel/verifier.py').read_bytes())==json.loads(frozen)['oracle_sha256']
            if json.loads((out/'results.json').read_text()) != results:
                raise IntegrityError('Trial evidence changed before publication')
            if agent and agent.frozen != model_intents:
                raise IntegrityError('Tool intent changed before publication')
            selection_outcomes = {}
            if investigate:
                for case in ['M1','M2']:
                    pair=[r['oracle_pass'] for r in results if r['case']==case]
                    selection_outcomes[case] = ('observed_regression_one_trial' if pair==[True,False]
                        else 'no_regression_observed_one_trial' if pair==[True,True] else 'inconclusive')
            guard.publish(out/'summary.json', {'investigator_calls':investigator.calls if investigator else 0,
                'selection_outcomes':selection_outcomes, 'status':'evaluated_g5_one_trial_slice' if investigate else'verified_g4_bounded_live_slice' if agent else 'verified_manual_fixture_matrix','worlds':len(results),'model_calls':agent.calls if agent else 0,'plan_hash':plan_hash, 'preflight_status':'reached_tool' if agent else 'not_applicable'})
    finally: (ROOT/DOMAIN).write_text(base_source)

if __name__=='__main__':
    if '--meta' in sys.argv or '--investigate' in sys.argv:
        from wheel.meta_agent import MetaAgent
        try: run(MetaAgent(), investigate='--investigate' in sys.argv)
        except Exception as error:
            print('Model experiment failed: ' + type(error).__name__ + '; inspect stage artifacts. No verification claimed.')
            if isinstance(error, RuntimeError): print(str(error))
            raise SystemExit(1) from None
    else: run()
