"""One paid, source-cited inventory investigation of an already JUnit-caught mutation."""
import argparse
import difflib
import hashlib
import html
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
from urllib.request import ProxyHandler, build_opener, install_opener

ROOT = Path(__file__).resolve().parents[1]
JAVA = 'services/inventory-api-java'
SOURCE = JAVA + '/src/main/java/dev/codexwheel/inventory/InventoryStore.java'
PEER = 'services/checkout-agent-python/checkout_agent/client.py'
POLICY = 'evaluation/inventory_investigation_v1.json'
MODEL = 'muse-spark-1.3'
PROMPT = '''Investigate the provided Java inventory change and unchanged Python checkout consumer.
Choose a short executable event sequence to test whether the change violates lifecycle or
allocation expectations. One SKU has stock 1. Only ACTIVE same-owner reservations may
confirm. EXPIRED/RELEASED reservations cannot confirm. One order per reservation.
This is a known author-prepared fixture already caught by conventional tests; do not claim
blind discovery or added coverage. You get one response, no execution feedback or repair.
Return JSON only: {"status":"proposed","reason":"brief source-grounded hypothesis",
"actions":[{"op":"RESERVE|TRIGGER_EXPIRY|CHECKOUT|RELEASE","buyer":"A|B"}],
"citations":[{"path":"exact supplied path","version":"base|candidate",
"start":1,"end":1,"quote":"exact inclusive source lines including indentation"}]}.
Use 2 to 8 actions. Each buyer has reservation rA/rB and order orderA/orderB. RESERVE must
precede other actions for that buyer. Repeats are allowed. Expiry is a privileged explicit
lifecycle event, not actual clock advancement or an in-flight race. Include an exact
candidate Java citation and an unchanged Python BASE citation, each at most 8 lines.
Source line numbers are one-based inclusive; preserve quote whitespace exactly.
Alternatively return {"status":"abstained","reason":"brief reason"}. No arbitrary URLs,
IDs, code, shell, extra keys or claimed runtime outcomes. The independent verifier decides
the outcome; a difference alone is not proof of a violation.'''


def sha(raw): return hashlib.sha256(raw).hexdigest()
def encoded(value): return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
def save(out, name, value): (out/name).write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def parse(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)


def validate(proposal, sources):
    if not isinstance(proposal, dict): raise ValueError('Expected object')
    if proposal.get('status') == 'abstained':
        if set(proposal) != {'status', 'reason'}: raise ValueError('Invalid abstention')
    else:
        if set(proposal) != {'status','reason','actions','citations'} or proposal['status'] != 'proposed':
            raise ValueError('Invalid proposal fields')
        actions = proposal['actions']
        if not isinstance(actions, list) or not 2 <= len(actions) <= 8: raise ValueError('Action limit')
        reserved = set()
        for action in actions:
            if not isinstance(action, dict) or set(action) != {'op','buyer'}: raise ValueError('Invalid action shape')
            if action['op'] not in ('RESERVE','TRIGGER_EXPIRY','CHECKOUT','RELEASE') or action['buyer'] not in ('A','B'):
                raise ValueError('Unsupported action')
            if action['op'] == 'RESERVE': reserved.add(action['buyer'])
            elif action['buyer'] not in reserved: raise ValueError('Reserve must precede use')
        citations = proposal['citations']
        if not isinstance(citations, list) or not 2 <= len(citations) <= 4: raise ValueError('Citation limit')
        cited = set()
        for citation in citations:
            if not isinstance(citation, dict) or set(citation) != {'path','version','start','end','quote'}:
                raise ValueError('Citation shape')
            path, version = citation['path'], citation['version']
            if path not in sources or version not in sources[path]: raise ValueError('Citation source')
            start, end = citation['start'], citation['end']
            lines = sources[path][version].splitlines()
            if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines) or end-start >= 8:
                raise ValueError('Citation bounds')
            if citation['quote'] != '\n'.join(lines[start-1:end]): raise ValueError('Citation quote')
            cited.add((path,version))
        if (SOURCE,'candidate') not in cited or (PEER,'base') not in cited: raise ValueError('Required source references')
    if not isinstance(proposal['reason'], str) or not 1 <= len(proposal['reason']) <= 2000: raise ValueError('Reason bound')
    return proposal


def command(args, cwd=ROOT, timeout=120):
    from wheel.experiment import child_env
    return subprocess.run(args, cwd=cwd, env=child_env(), capture_output=True, text=True, timeout=timeout, check=True).stdout


def admit(protocol):
    registration = json.loads((ROOT/'evaluation/inventory_candidate_v1.json').read_text())
    base, candidate = protocol['base'], protocol['candidate']
    command(['git','fetch','origin',base,candidate])
    if registration['baseline_commit'] != base: raise ValueError('Baseline identity')
    changed = command(['git','diff','--name-only',base,candidate]).splitlines()
    if changed != [SOURCE]: raise ValueError('Unsupported revision pair')
    sources = {}
    for path, expected in registration['baseline_files'].items():
        raw = command(['git','show',base+':'+path])
        if sha(raw.encode()) != expected: raise ValueError('Baseline bytes differ')
        other = command(['git','show',candidate+':'+path])
        target = registration['candidate_source_sha256'] if path == SOURCE else expected
        if sha(other.encode()) != target: raise ValueError('Candidate or unchanged peer/tests differ')
        if not (ROOT/path).is_file() or sha((ROOT/path).read_bytes()) != expected:
            raise ValueError('Current trusted baseline file differs')
        if path in (SOURCE, PEER): sources[path] = {'base':raw, 'candidate':other}
    return sources, registration


def select(client, sources, out, protocol):
    numbered = {path:{version:'\n'.join(f'{i}: {line}' for i,line in enumerate(text.splitlines(),1))
                       for version,text in versions.items()} for path,versions in sources.items()}
    packet = {'sources':numbered, 'diff':'\n'.join(difflib.unified_diff(
        sources[SOURCE]['base'].splitlines(), sources[SOURCE]['candidate'].splitlines(), fromfile='base', tofile='candidate'))}
    request = {'model':MODEL,'max_completion_tokens':protocol['max_completion_tokens'],'reasoning_effort':'low',
               'messages':[{'role':'developer','content':PROMPT},{'role':'user','content':json.dumps(packet)}]}
    if len(json.dumps(request)) > 100000: raise ValueError('Request character cap')
    receipt = {'ordinal':1,'status':'attempted','request':request,'numeric_usd_cost':None}
    path = out/'model-request.json'
    with path.open('x') as stream: json.dump(receipt,stream,indent=2)
    try:
        response = client.chat.completions.create(**request)
        receipt.update(status='response_received',response_id=response.id,model=response.model,
                       usage=response.usage.model_dump() if response.usage else None,
                       response=response.model_dump(exclude_none=True))
        if response.model != MODEL or len(response.choices) != 1 or response.choices[0].finish_reason != 'stop':
            raise ValueError('Unexpected or incomplete response')
        proposal = validate(parse(response.choices[0].message.content),sources)
        receipt['admission'] = proposal['status']
        return proposal
    except Exception as error:
        receipt.update(status='rejected_or_error',error_type=type(error).__name__)
        raise
    finally: save(out,'model-request.json',receipt)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name,path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


def build(protocol, scratch, out):
    jars = {}
    for side, revision in [('base',protocol['base']),('candidate',protocol['candidate'])]:
        work = scratch/side; work.mkdir()
        # Copy reviewed Java sources only; never run a candidate checkout/workflow or its scripts.
        files = command(['git','ls-tree','-r','--name-only',protocol['base'],JAVA]).splitlines()
        for path in files:
            if path.endswith('.gitignore'): continue
            dest = work/Path(path).relative_to(JAVA); dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_text(command(['git','show',revision+':'+path]))
        from wheel.experiment import child_env
        test = subprocess.run(['mvn','-B','test'],cwd=work,env=child_env(),capture_output=True,text=True,timeout=180)
        (out/(side+'-tests.log')).write_text(test.stdout+test.stderr)
        save(out,side+'-tests.json',{'returncode':test.returncode,'tests_unchanged':True})
        if side == 'base' and test.returncode: raise ValueError('Invalid baseline tests')
        # Candidate catches are retained above. Packaging permits observation, not promotion.
        package = command(['mvn','-B','-DskipTests','package'],cwd=work,timeout=180)
        (out/(side+'-package.log')).write_text(package)
        jars[side] = work/'target/inventory-api-java-0.1.0-SNAPSHOT.jar'
    return jars


def world(runtime, jar, directory, actions, client_module, oracle):
    from wheel.experiment import child_env
    from wheel.isolation import docker
    import httpx
    directory.mkdir()
    name = runtime.network+'-'+secrets.token_hex(5); runtime.names.add(name)
    token = secrets.token_hex(32); trace = []
    try:
        subprocess.run(['docker','run','-d','--name',name,*runtime.limits(),'--network',runtime.network,
                        '--mount',f'type=bind,src={jar},dst=/app.jar,readonly',
                        '--mount',f'type=bind,src={directory},dst=/state',
                        '-e','WHEEL_INVENTORY_EVALUATOR_TOKEN','-e','WHEEL_INVENTORY_STATE=/state/state.json',
                        runtime.images['java'],'java','-XX:ActiveProcessorCount=1','-jar','/app.jar',
                        '--server.address=0.0.0.0'],env={**child_env(),'WHEEL_INVENTORY_EVALUATOR_TOKEN':token},
                       capture_output=True,text=True,check=True,timeout=30)
        data = json.loads(docker('inspect',name).stdout)[0]; config = data['HostConfig']
        if (data['Image'] != runtime.images['java'] or not config['ReadonlyRootfs'] or config['Privileged']
                or config['NetworkMode'] != runtime.network or data['Config']['User'] != runtime.uid
                or 'ALL' not in config['CapDrop'] or 'no-new-privileges' not in config['SecurityOpt']
                or config['Memory'] != 512*1024*1024 or config['PidsLimit'] != 128 or config['NanoCpus'] != 1000000000):
            raise ValueError('Inventory container configuration drift')
        host = data['NetworkSettings']['Networks'][runtime.network]['IPAddress']
        url = 'http://'+host+':8081'
        for _ in range(150):
            try:
                if httpx.get(url+'/health',timeout=.5,trust_env=False).status_code == 200: break
            except httpx.TransportError: pass
            time.sleep(.2)
        else: raise RuntimeError('Inventory readiness timeout')
        client = client_module.CheckoutClient(url); accepted = []; runtime_error = False
        for index, action in enumerate(actions):
            buyer = action['buyer']; reservation = 'r'+buyer; op = action['op']
            row = {'index':index,'action':action}
            try:
                if op == 'RESERVE': value = client.reserve(reservation,buyer)
                elif op == 'CHECKOUT':
                    value = client.checkout(reservation,buyer,'order'+buyer); accepted.append(value)
                elif op == 'RELEASE': value = client.release(reservation,buyer)
                else:
                    response = httpx.post(url+'/internal/evaluator/trigger-expiry',headers={'X-Evaluator-Token':token},
                                          json={'reservationId':reservation},timeout=5,trust_env=False)
                    if response.status_code != 200: raise client_module.InventoryRejected(response.status_code,response.json().get('error'))
                    value = response.json()
                row.update(status='returned',value=value)
            except client_module.InventoryRejected as error:
                row.update(status='rejected',http_status=error.status,code=error.code)
                runtime_error |= error.status >= 500
            trace.append(row)
            save(directory,'action-trace.json',trace)
        response = httpx.get(url+'/internal/evaluator/state',headers={'X-Evaluator-Token':token},timeout=5,trust_env=False)
        response.raise_for_status(); snapshot = response.json()
        persisted = json.loads((directory/'state.json').read_text())
        if snapshot != persisted: raise ValueError('Evaluator state differs from committed file')
        result = {'trace':trace,'snapshot':snapshot,'accepted_orders':accepted,'jar_sha256':sha(jar.read_bytes()),
                  'image':runtime.images['java'],'execution':'fresh_container_with_trusted_host_peer'}
        try:
            result['verification'] = oracle.verify(snapshot,accepted)
            result['status'] = 'execution_error' if runtime_error else 'pass'
        except ValueError as error:
            result.update(status='contract_violation',violation=str(error))
        save(directory,'world.json',result)
        return result
    except Exception as error:
        save(directory,'execution-error.json',{'error_type':type(error).__name__,'trace':trace})
        raise
    finally:
        if runtime.exists(name):
            with (directory/'java.log').open('w') as log: runtime.stop_java(name,log)
        runtime.names.discard(name)


def verdict(rows):
    if len(rows) != 6: return 'inconclusive'
    paired = [(rows[i]['status'],rows[i+1]['status']) for i in range(0,6,2)]
    if all(a == 'pass' and b == 'contract_violation' for a,b in paired): return 'reproduced_regression'
    if all(a == b == 'pass' for a,b in paired): return 'not_reproduced'
    if any(a != 'pass' for a,b in paired): return 'invalid_baseline'
    if any(b == 'execution_error' for a,b in paired): return 'execution_error'
    return 'inconclusive'


def run(expected, output):
    from wheel.meta_agent import MetaAgent
    from wheel.plan_guard import PlanGuard
    from wheel.isolation import DockerRuntime
    out = Path(output).absolute(); out.mkdir(exist_ok=False)
    summary = {'status':'started','new_model_calls':0,'worlds':0,'prior_conventional_result':'caught_by_existing_junit',
               'limits':['Known author-prepared mutation','Explicit expiry events, not clock/race proof',
                         'Trusted unchanged Python host peer; producer container confinement',
                         'No repair, automatic merge, added coverage or AI necessity claim']}
    runtime = None
    try:
        client = MetaAgent(max_calls=1).client  # Remove model key before build/runtime subprocesses.
        protocol = json.loads((ROOT/POLICY).read_text())
        if command(['git','rev-parse','HEAD']).strip() != expected: raise ValueError('Implementation revision')
        sources, registration = admit(protocol)
        protected = list((ROOT/'wheel').glob('*.py')) + [ROOT/p for p in registration['baseline_files']] + [ROOT/POLICY, ROOT/'evaluation/inventory_candidate_v1.json',ROOT/'.github/workflows/inventory-investigation.yml']
        for path in protected:
            relative = path.relative_to(ROOT).as_posix()
            if path.is_symlink() or command(['git','show',expected+':'+relative]).encode() != path.read_bytes():
                raise ValueError('Uncommitted implementation input')
        save(out,'source-snapshots.json',sources)
        control = [{'op':'RESERVE','buyer':'A'},{'op':'CHECKOUT','buyer':'A'}]
        lock = {'implementation':expected,'protocol':protocol,'sources':{p:{v:sha(s.encode()) for v,s in versions.items()} for p,versions in sources.items()},'control':control}
        save(out,'implementation-lock.json',lock)
        guard = PlanGuard(out/'implementation-lock.json',(out/'implementation-lock.json').read_bytes(),protected)
        guard.bind(out/'source-snapshots.json',(out/'source-snapshots.json').read_bytes())
        client_module = module('inventory_peer',ROOT/PEER)
        oracle = module('inventory_oracle',ROOT/'services/checkout-agent-python/checkout_agent/verifier.py')
        install_opener(build_opener(ProxyHandler({})))
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory)
            jars = build(protocol,scratch,out)
            for jar in jars.values(): guard.bind(jar,jar.read_bytes())
            runtime = DockerRuntime(ROOT,scratch)
            save(out,'runtime-images.json',runtime.prepare()); save(out,'confinement.json',runtime.probe())
            def execute(label, actions):
                rows = []
                for trial in range(3):
                    for side in ('base','candidate'):
                        guard.verify(label+'-'+str(trial)+'-'+side)
                        if summary['worlds'] >= protocol['world_cap']: raise ValueError('World cap')
                        summary['worlds'] += 1
                        result = world(runtime,jars[side],out/(label+'-'+str(trial)+'-'+side),actions,client_module,oracle)
                        result.update(side=side,trial=trial); rows.append(result)
                        save(out,label+'-worlds.json',rows)
                return rows
            controls = execute('control',control)
            if verdict(controls) != 'not_reproduced': raise ValueError('Invalid control; no paid request')
            summary['new_model_calls'] = 1
            proposal = select(client,sources,out,protocol)
            save(out,'proposal.json',proposal); guard.bind(out/'proposal.json',(out/'proposal.json').read_bytes())
            if proposal['status'] == 'abstained': summary['status'] = 'abstained'
            else:
                rows = execute('selected',proposal['actions']); summary['status'] = verdict(rows)
                summary['selected_plan_sha256'] = sha(encoded(proposal))
            save(out,'integrity-checks.json',guard.checks)
    except Exception as error:
        summary.update(status='rejected_or_execution_error',error_type=type(error).__name__)
        raise
    finally:
        summary['new_model_calls'] = int((out/'model-request.json').exists())
        save(out,'summary.json',summary)
        (out/'report.html').write_text('<!doctype html><meta charset="utf-8"><title>Inventory investigation</title><h1>Inventory investigation</h1><p>Known defect already caught by JUnit. No extra coverage or oversell claim.</p><pre>'+html.escape(json.dumps(summary,indent=2))+'</pre><p>Inspect proposal.json, model-request.json and selected/control-worlds.json for source references, requests and actual lifecycle records.</p>')
        if runtime is not None: runtime.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected',required=True); parser.add_argument('--output',required=True)
    args = parser.parse_args(); run(args.expected,args.output)
