"""Manually frozen synthetic counterfactuals. No model calls or AI discovery."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time

import httpx
from wheel.proxy import Gateway
from wheel.verifier import check

ROOT = Path(__file__).resolve().parents[1]
JAVA = 'services/refund-api-java'
CLIENT = 'services/support-agent-python/refund_tool/client.py'
DOMAIN = JAVA + '/src/main/java/dev/codexwheel/refunds/domain/RefundService.java'

def digest(data): return hashlib.sha256(data).hexdigest()
def port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0)); return s.getsockname()[1]

def start(jar, ledger, token, log):
    p = port()
    process = subprocess.Popen(['java', '-jar', str(jar), '--server.port='+str(p)],
        env={**os.environ, 'WHEEL_LEDGER_PATH':str(ledger), 'WHEEL_EVALUATOR_TOKEN':token}, stdout=log, stderr=subprocess.STDOUT)
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

def run():
    out = ROOT/'evidence'; out.mkdir(exist_ok=True)
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
    frozen = json.dumps({'plans':plans, 'java':{k:digest(v.encode()) for k,v in variants.items()},
        'python':{k:digest(v.encode()) for k,v in wrappers.items()},
        'oracle_sha256':digest((ROOT/'wheel/verifier.py').read_bytes()),
        'proxy_sha256':digest((ROOT/'wheel/proxy.py').read_bytes()),
        'commit':os.getenv('GITHUB_SHA','local'), 'trials':3},sort_keys=True).encode()
    (out/'frozen-plan.json').write_bytes(frozen)
    plan_hash=digest(frozen)
    results=[]
    try:
        with tempfile.TemporaryDirectory() as td:
            td=Path(td); jars={}
            for name, source in variants.items():
                (ROOT/DOMAIN).write_text(source)
                subprocess.run(['mvn','-B','-f',str(ROOT/JAVA/'pom.xml'), 'clean','package','-DskipTests'], check=True)
                jar=td/(name+'.jar'); jar.write_bytes((ROOT/JAVA/'target/refund-api-java-0.1.0-SNAPSHOT.jar').read_bytes()); jars[name]=jar
                (out/(name+'.java')).write_text(source)
            for name, source in wrappers.items(): (out/(name+'-client.py')).write_text(source)
            for plan in plans:
                for trial in range(3):
                    pair=[]
                    for world in ['base','candidate']:
                        case=plan['case']; label=f'{case}-{plan["action"]}-{trial}-{world}'
                        java_variant=case if world=='candidate' and case in variants else 'base'
                        py_variant=case if world=='candidate' and case in wrappers else 'base'
                        module_file=td/(py_variant+'.py'); module_file.write_text(wrappers[py_variant])
                        spec=importlib.util.spec_from_file_location('trial_client',module_file)
                        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
                        ledger=td/(label+'.tsv'); token=secrets.token_hex(32)
                        authorization={'order_id':'ORD-SYN-TRIAL','amount_minor_units':plan['amount']}
                        rule={'action':plan['action'],'min':plan['amount'],'max':plan['amount']}
                        with (out/(label+'.log')).open('w') as log:
                            process,p=start(jars[java_variant],ledger,token,log)
                            try:
                                assert snapshot(p, token)==[]
                                with Gateway(p,rule) as gateway:
                                    transport_errors=[]
                                    class ObservedClient(httpx.Client):
                                        def send(self, *args, **kwargs):
                                            try: return super().send(*args, **kwargs)
                                            except httpx.TransportError as error:
                                                transport_errors.append(type(error).__name__)
                                                raise
                                    with ObservedClient(base_url=f'http://127.0.0.1:{gateway.port}',trust_env=False,timeout=3) as client:
                                        receipt=module.RefundTool(client=client).issue_refund(**authorization)
                                    events=list(gateway.events)
                                assert bool(transport_errors)==(plan['action']=='DROP_DOWNSTREAM_BEFORE_RESPONSE')
                                effects=snapshot(p,token)
                                assert len(events)==(1 if plan['action']=='PASS_THROUGH' else 2)
                                assert all(e['upstream_status']==200 for e in events)
                                assert events[0]['upstream_body']['refund_effect_id']==effects[0]['effect_id']
                                assert events[0]['action']==plan['action']
                                keys=[e['key_sha256'] for e in events]
                                expected_change=world=='candidate' and case=='M2' and plan['action']!='PASS_THROUGH'
                                assert (len(set(keys))==2)==expected_change
                            finally: stop(process)
                            # Restart checks persisted effects and stable-key dedup recovery.
                            process,p=start(jars[java_variant],ledger,token,log)
                            try: assert snapshot(p,token)==effects
                            finally: stop(process)
                        valid=check(effects,authorization)
                        record=dict(label=label, case=case,world=world,trial=trial,plan_hash=plan_hash,
                            transport_errors=transport_errors,oracle_pass=valid,effects=effects,events=events,receipt=receipt,
                            restart_recovered=True,java_sha256=digest(variants[java_variant].encode()),
                            python_sha256=digest(wrappers[py_variant].encode()))
                        results.append(record);pair.append(valid)
                        (out/'results.json').write_text(json.dumps(results,indent=2))
                    expected_regression=plan['case'] in ['M1','M2'] and plan['action']!='PASS_THROUGH'
                    assert pair==[True,not expected_regression], (plan,pair)
            assert digest((out/'frozen-plan.json').read_bytes())==plan_hash
            assert digest((ROOT/'wheel/verifier.py').read_bytes())==json.loads(frozen)['oracle_sha256']
            (out/'summary.json').write_text(json.dumps({'status':'verified_manual_fixture_matrix','worlds':len(results),'model_calls':0,'plan_hash':plan_hash},indent=2))
    finally: (ROOT/DOMAIN).write_text(base_source)

if __name__=='__main__': run()
