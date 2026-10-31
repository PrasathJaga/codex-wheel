"""Authenticated inventory failure -> one bounded Meta restoration -> fresh verification."""
import argparse
import html
import json
from pathlib import Path
import shutil
import tempfile
from urllib.request import ProxyHandler, build_opener, install_opener

ROOT = Path(__file__).resolve().parents[1]
POLICY = 'evaluation/inventory_repair_v1.json'
MODEL = 'muse-spark-1.3'
PROMPT = '''Propose one bounded restoration of the supplied inventory candidate to the supplied
healthy baseline. The existing tests already caught the defect; this is not unfamiliar repair.
You receive the actual frozen experiment and freshly reproduced failing records. Return JSON
only with exactly old_text, new_text, reason. old_text must occur exactly once in the candidate.
Replace that one span to restore the ACTIVE-state rejection in confirm. No path, tests,
ownership, persistence, oracle, evaluator or other edits. The entire resulting Java file must
equal healthy source exactly. Preserve indentation/newlines. No markdown or runtime claims.
One response, no retries or verification feedback.'''


def apply_proposal(proposal, candidate, healthy):
    if not isinstance(proposal, dict) or set(proposal) != {'old_text','new_text','reason'}:
        raise ValueError('Repair proposal shape')
    if any(not isinstance(proposal[k], str) or not 1 <= len(proposal[k]) <= 5000 for k in proposal):
        raise ValueError('Repair text bounds')
    if candidate.count(proposal['old_text']) != 1: raise ValueError('Repair span is not unique')
    restored = candidate.replace(proposal['old_text'],proposal['new_text'],1)
    if restored != healthy or restored == candidate: raise ValueError('Repair differs from allowed healthy restoration')
    return restored


def select(client, packet, out, protocol):
    from wheel.inventory_investigation import parse, save
    request = {'model':MODEL,'max_completion_tokens':protocol['max_completion_tokens'],'reasoning_effort':'low',
               'messages':[{'role':'developer','content':PROMPT},{'role':'user','content':json.dumps(packet)}]}
    if len(json.dumps(request)) > 100000: raise ValueError('Repair request character cap')
    record = {'ordinal':1,'status':'attempted','request':request,'numeric_usd_cost':None}
    with (out/'repair-request.json').open('x') as stream: json.dump(record,stream,indent=2)
    try:
        response = client.chat.completions.create(**request)
        record.update(status='response_received',response_id=response.id,model=response.model,
                      usage=response.usage.model_dump() if response.usage else None,response=response.model_dump(exclude_none=True))
        if response.model != MODEL or len(response.choices) != 1 or response.choices[0].finish_reason != 'stop':
            raise ValueError('Unexpected or incomplete repair response')
        return parse(response.choices[0].message.content)
    except Exception as error:
        record.update(status='request_error',error_type=type(error).__name__)
        raise
    finally: save(out,'repair-request.json',record)


def authenticate(origin, destination, protocol, sources, oracle, inv):
    from wheel.repair_link import unpack
    unpack(origin,protocol['origin_sha256'],destination)
    read = lambda name: json.loads((destination/name).read_text())
    summary = read('summary.json'); lock = read('implementation-lock.json'); proposal = read('proposal.json')
    if summary['status'] != 'reproduced_regression' or summary['new_model_calls'] != 1 or summary['worlds'] != 12:
        raise ValueError('Parent cycle identity')
    if read('source-snapshots.json') != sources: raise ValueError('Parent source identity')
    if lock['implementation'] != protocol['origin_implementation'] or lock['protocol']['base'] != protocol['base'] or lock['protocol']['candidate'] != protocol['candidate']:
        raise ValueError('Parent implementation/revisions')
    inv.validate(proposal,sources)
    if inv.sha(inv.encoded(proposal)) != summary['selected_plan_sha256'] or summary['selected_plan_sha256'] != protocol['selected_plan_sha256']:
        raise ValueError('Parent selected plan identity')
    for path, versions in sources.items():
        for version,text in versions.items():
            if inv.sha(text.encode()) != lock['sources'][path][version]: raise ValueError('Parent source digest')
    for label, expected in [('control','not_reproduced'),('selected','reproduced_regression')]:
        rows = read(label+'-worlds.json')
        # Use a source-independent verifier; preserve original files and actual actions.
        if len(rows) != 6: raise ValueError('Incomplete parent worlds')
        for index,row in enumerate(rows):
            if (row['trial'],row['side']) != (index//2,('base','candidate')[index%2]): raise ValueError('Parent pair identity')
            folder = destination/(label+'-'+str(row['trial'])+'-'+row['side'])
            if row['snapshot'] != json.loads((folder/'state.json').read_text()) or row['trace'] != json.loads((folder/'action-trace.json').read_text()):
                raise ValueError('Parent state/trace mismatch')
            expected_actions = lock['control'] if label == 'control' else proposal['actions']
            if [r['action'] for r in row['trace']] != expected_actions: raise ValueError('Parent execution differs from plan')
            try: actual = oracle.verify(row['snapshot'],row['accepted_orders'])
            except ValueError as error:
                if row['status'] != 'contract_violation' or row.get('violation') != str(error): raise ValueError('Parent violation mismatch')
            else:
                if row['status'] != 'pass' or row['verification'] != actual: raise ValueError('Parent pass mismatch')
        if inv.verdict(rows) != expected: raise ValueError('Parent verdict mismatch')
    if read('base-tests.json')['returncode'] != 0 or read('candidate-tests.json')['returncode'] == 0:
        raise ValueError('Parent conventional test provenance')
    return proposal, lock['control']


def run(expected, origin, output):
    from wheel import inventory_investigation as inv
    from wheel.meta_agent import MetaAgent
    from wheel.plan_guard import PlanGuard
    from wheel.isolation import DockerRuntime
    out = Path(output).absolute(); out.mkdir(exist_ok=False)
    state = {'status':'started','new_model_calls':0,'new_worlds':0,'historical_parent_worlds':12,
             'claim':'Known supplied-answer healthy baseline restoration, not unfamiliar repair',
             'prior_conventional_result':'caught_by_existing_junit'}
    runtime = None
    try:
        client = MetaAgent(max_calls=1).client
        protocol = json.loads((ROOT/POLICY).read_text())
        if inv.command(['git','rev-parse','HEAD']).strip() != expected: raise ValueError('Implementation revision')
        sources, registration = inv.admit(protocol)
        oracle = inv.module('inventory_repair_oracle',ROOT/'services/checkout-agent-python/checkout_agent/verifier.py')
        parent = out/'parent'; parent.mkdir()
        proposal, control = authenticate(Path(origin),parent,protocol,sources,oracle,inv)
        shutil.copyfile(origin,out/'origin-investigation.zip')
        selected = proposal['actions']
        lock = {'implementation':expected,'protocol':protocol,'selected_plan':proposal,'control':control,
                'source_hashes':{p:{v:inv.sha(s.encode()) for v,s in versions.items()} for p,versions in sources.items()}}
        inv.save(out,'repair-lock.json',lock); inv.save(out,'source-snapshots.json',sources)
        protected = list((ROOT/'wheel').glob('*.py')) + [ROOT/p for p in registration['baseline_files']] + [ROOT/POLICY,ROOT/inv.POLICY,ROOT/'evaluation/inventory_candidate_v1.json',ROOT/'.github/workflows/inventory-repair.yml']
        for path in protected:
            relative = path.relative_to(ROOT).as_posix()
            if path.is_symlink() or inv.command(['git','show',expected+':'+relative]).encode() != path.read_bytes():
                raise ValueError('Uncommitted repair input')
        guard = PlanGuard(out/'repair-lock.json',(out/'repair-lock.json').read_bytes(),protected)
        for path in [out/'origin-investigation.zip',out/'source-snapshots.json',*parent.rglob('*')]:
            if path.is_file(): guard.bind(path,path.read_bytes())
        peer = inv.module('inventory_repair_peer',ROOT/inv.PEER)
        install_opener(build_opener(ProxyHandler({})))
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory)
            jars = inv.build(protocol,scratch,out)
            for jar in jars.values(): guard.bind(jar,jar.read_bytes())
            runtime = DockerRuntime(ROOT,scratch)
            inv.save(out,'runtime-images.json',runtime.prepare()); inv.save(out,'confinement.json',runtime.probe())
            def stage(label, stage_jars):
                outcomes = {}
                for plan_name,actions in [('control',control),('selected',selected)]:
                    rows = []
                    for trial in range(3):
                        for side in ('base','candidate'):
                            guard.verify(label+'-'+plan_name+'-'+str(trial)+'-'+side)
                            if state['new_worlds'] >= protocol['world_cap']: raise ValueError('Repair world cap')
                            state['new_worlds'] += 1
                            row = inv.world(runtime,stage_jars[side],out/(label+'-'+plan_name+'-'+str(trial)+'-'+side),actions,peer,oracle)
                            row.update(trial=trial,side=side);rows.append(row)
                            inv.save(out,label+'-'+plan_name+'-worlds.json',rows)
                    outcomes[plan_name] = inv.verdict(rows)
                return outcomes
            broken = stage('broken',jars); state['broken'] = broken
            if broken != {'control':'not_reproduced','selected':'reproduced_regression'}:
                raise ValueError('Fresh original failure was not reproduced; no repair call')
            packet = {'healthy_source':sources[inv.SOURCE]['base'],'candidate_source':sources[inv.SOURCE]['candidate'],
                      'source_path':inv.SOURCE,'frozen_experiment':proposal,
                      'fresh_failing_worlds':[r for r in json.loads((out/'broken-selected-worlds.json').read_text()) if r['side']=='candidate'],
                      'editing_boundary':'One unique replacement; whole resulting source must equal supplied healthy bytes'}
            guard.verify('before_repair_request')
            repair = select(client,packet,out,protocol)
            inv.save(out,'repair-proposal.json',repair)
            restored = apply_proposal(repair,sources[inv.SOURCE]['candidate'],sources[inv.SOURCE]['base'])
            inv.save(out,'repair-admission.json',{'status':'admitted','source_sha256':inv.sha(restored.encode())})
            (out/'restored-InventoryStore.java').write_text(restored);guard.bind(out/'restored-InventoryStore.java',restored.encode())
            guard.bind(out/'repair-proposal.json',(out/'repair-proposal.json').read_bytes())
            work = scratch/'restored'
            shutil.copytree(scratch/'candidate',work,ignore=shutil.ignore_patterns('target'))
            source = work/Path(inv.SOURCE).relative_to(inv.JAVA);source.write_text(restored)
            for path in work.rglob('*'):
                if path.is_file(): guard.bind(path,path.read_bytes())
            guard.verify('before_repair_tests')
            from wheel.experiment import child_env
            import subprocess
            tests = subprocess.run(['mvn','-B','verify'],cwd=work,env=child_env(),capture_output=True,text=True,timeout=180)
            (out/'repair-tests.log').write_text(tests.stdout+tests.stderr)
            inv.save(out,'repair-tests.json',{'returncode':tests.returncode,'source_sha256':inv.sha(source.read_bytes()),'tests_unchanged':True})
            if tests.returncode: raise ValueError('Repair tests failed')
            repaired_jar = work/'target/inventory-api-java-0.1.0-SNAPSHOT.jar';guard.bind(repaired_jar,repaired_jar.read_bytes())
            state['repaired'] = stage('repaired',{'base':jars['base'],'candidate':repaired_jar})
            if state['repaired'] != {'control':'not_reproduced','selected':'not_reproduced'}:
                raise ValueError('Repair did not pass repeated verification')
            guard.verify('before_repair_summary');inv.save(out,'integrity-checks.json',guard.checks)
            state.update(status='verified_bounded_inventory_restoration',repair_sha256=inv.sha(restored.encode()),
                         selected_plan_sha256=protocol['selected_plan_sha256'])
    except Exception as error:
        state.update(status='rejected_or_execution_error',error_type=type(error).__name__)
        raise
    finally:
        state['new_model_calls'] = int((out/'repair-request.json').exists())
        inv.save(out,'summary.json',state)
        (out/'report.html').write_text('<!doctype html><meta charset="utf-8"><title>Inventory repair</title><h1>Inventory bounded restoration</h1><p>Healthy answer supplied; existing JUnit already caught the defect. Original failure remains in parent/ and origin-investigation.zip.</p><pre>'+html.escape(json.dumps(state,indent=2))+'</pre>')
        if runtime is not None: runtime.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected',required=True);parser.add_argument('--origin',required=True);parser.add_argument('--output',required=True)
    args = parser.parse_args();run(args.expected,args.origin,args.output)
