"""One fresh, bounded M1 PR-to-restoration cycle. No archived inference/world reuse."""
import argparse
import copy
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace


class CycleLedger:
    def __init__(self,client,path):
        self.client=client;self.path=Path(path);self.attempts=[]
    def scoped(self,role):
        limits={'investigation':6,'diagnosis':1,'repair':1}
        if role not in limits:raise ValueError('Unknown role')
        def create(**kwargs):
            if len(self.attempts)>=8 or sum(a['role']==role for a in self.attempts)>=limits[role]:raise RuntimeError('Cycle request cap reached')
            if kwargs.get('model')!='muse-spark-1.3' or kwargs.get('max_completion_tokens')!=2048 or kwargs.get('reasoning_effort')!='low':raise ValueError('Unexpected request policy')
            if len(json.dumps(kwargs['messages']))>100000:raise ValueError('Request character cap')
            row={'role':role,'ordinal':len(self.attempts)+1,'status':'attempted','request':copy.deepcopy(kwargs)}
            self.attempts.append(row);self.persist()
            try:
                response=self.client.chat.completions.create(**kwargs)
                row.update(status='response_received',response_id=response.id,model=response.model,
                           usage=response.usage.model_dump() if response.usage else None,response=response.model_dump(exclude_none=True))
                if response.model!='muse-spark-1.3':raise ValueError('Unexpected response model')
                return response
            except Exception as error:
                row.update(status='request_error',error_type=type(error).__name__);raise
            finally:self.persist()
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    def persist(self):self.path.write_text(json.dumps(self.attempts,indent=2))


def run(number,expected,output):
    from wheel.experiment import ROOT,DOMAIN,CLIENT,digest
    from wheel.intake import inspect,git
    from wheel.pr_review import github_api,identity
    from wheel.evaluation import implementation_lock,save
    from wheel.g6 import build_jars
    from wheel.expanded_domain import investigate,plan,execute
    from wheel.interface_followup import prompt_client,protocol as interface_protocol
    from wheel.meta_agent import MetaAgent
    from wheel.isolation import DockerRuntime
    from wheel.plan_guard import PlanGuard,IntegrityError
    from wheel.repeatability import POLICY
    from wheel import patcher,diagnosis,business_dashboard,report_visualizer
    token=os.environ.pop('GH_TOKEN','');api=github_api(token)
    out=Path(output).absolute();out.mkdir(exist_ok=False)
    state={'schema':'codex-wheel.fresh-pr-cycle.v1','status':'started','pr':number,'worlds':0,'new_model_calls':0,
           'limits':['Known author-seeded M1 case only','Healthy source supplied for exact restoration',
                     'No general AI superiority or unfamiliar-bug discovery','No automatic merge; finite tested conditions only']}
    runtime=None;ledger=None
    try:
        pr=api('GET',f'/pulls/{number}');base,head=identity(pr);state.update(base=base,head=head)
        if pr['state']!='open' or pr['head']['repo']['full_name']!='PrasathJaga/codex-wheel':raise IntegrityError('Unsupported PR')
        git(ROOT,'fetch','origin',base,head)
        admission=inspect(ROOT,base,head,'java')
        if admission['case']!='M1':raise IntegrityError('Cycle supports exact M1 only')
        save(out,'admission.json',admission)
        protocol=json.loads((ROOT/'evaluation/pr_cycle_v1.json').read_text())
        commit,paths=implementation_lock({'core_budget':protocol['caps']},expected,out)
        guard=PlanGuard(out/'implementation-lock.json',(out/'implementation-lock.json').read_bytes(),paths)
        for name in ['evaluation/pr_cycle_v1.json','.github/workflows/pr-cycle.yml']:
            guard.bind(ROOT/name,(ROOT/name).read_bytes())
        view={DOMAIN:admission['java'],CLIENT:admission['python']}
        save(out,'source-snapshots.json',view)
        guard.bind(out/'source-snapshots.json',(out/'source-snapshots.json').read_bytes())
        client=MetaAgent(max_calls=8).client;ledger=CycleLedger(client,out/'request-attempts.json')
        spec=investigate(prompt_client(ledger.scoped('investigation'),interface_protocol()['arms'][1]['developer_prompt']),view,protocol,out/'investigator-traces.json')
        save(out,'proposal.json',spec);guard.bind(out/'proposal.json',(out/'proposal.json').read_bytes())
        plans=[plan(protocol,view,spec,'C4',0),plan(protocol,view,spec,'C4',1,True)]
        with tempfile.TemporaryDirectory() as directory:
            scratch=Path(directory);runtime=DockerRuntime(ROOT,scratch)
            images=runtime.prepare();runtime.probe()
            java={'base':view[DOMAIN]['base'],'M1':view[DOMAIN]['candidate']};python={'base':view[CLIENT]['base']}
            jars=build_jars(java,scratch)
            for jar in jars.values():guard.bind(jar,jar.read_bytes())
            def stage(name,items,java_sources,runtime_jars):
                root=out/name;root.mkdir();work=scratch/name;work.mkdir()
                frozen={'commit':commit,'plans':items,'images':images,'build_hashes':{k:digest(v.read_bytes()) for k,v in runtime_jars.items()}}
                save(root,'locked-comparison.json',frozen)
                raw=(root/'locked-comparison.json').read_bytes();guard.bind(root/'locked-comparison.json',raw)
                manifest={**frozen,'policy':POLICY,'plan_hash':digest(raw)}
                rows,outcomes=execute(items,{'case':'M1','trials':3,'caps':{'worlds':12}},runtime,runtime_jars,java_sources,python,root,work,guard,manifest)
                for path in root.iterdir():guard.bind(path,path.read_bytes())
                state['worlds']+=len(rows)
                return frozen,rows,outcomes,digest(raw)
            frozen,rows,outcomes,plan_sha=stage('broken',plans,java,jars)
            if outcomes[plans[0]['id']]['verdict']!='reproduced_regression' or outcomes[plans[1]['id']]['verdict']!='not_reproduced':raise IntegrityError('Fresh regression/control gate failed')
            export={'frozen':frozen,'plans':[{'id':k,'verdict':v} for k,v in outcomes.items()], 'worlds':rows,
                    'provenance':{'activity':'fresh_current_cycle','plan_sha256':plan_sha},'supporting_records':{'source-snapshots.json':view},'limits':state['limits']}
            doc=diagnosis.packet(export,plans[0]['id'])
            explanation=diagnosis.request_diagnosis(ledger.scoped('diagnosis'),doc,out/'diagnosis.json')
            if explanation['status']!='explained':raise IntegrityError('Diagnosis was not admitted; preserved without retry')
            guard.bind(out/'diagnosis.json',(out/'diagnosis.json').read_bytes())
            failures=[r for r in rows if r['plan_id']==plans[0]['id'] and r['world']=='candidate']
            repair=patcher.propose(ledger.scoped('repair'),view,failures)
            save(out,'repair-proposal.json',repair)
            restored=patcher.apply_proposal(repair,view[DOMAIN]['candidate'],patcher.protocol())
            (out/'restored-RefundService.java').write_text(restored)
            guard.bind(out/'restored-RefundService.java',restored.encode())
            patcher.admitted_tests(restored,scratch,out)
            repaired_plans=copy.deepcopy(plans)
            for item in repaired_plans:item['source_hashes']['java']['candidate']=digest(restored.encode())
            repaired_java={**java,'M1':restored};repaired_jars={**jars,'M1':jars['base']}
            _,new_rows,new_outcomes,new_sha=stage('repaired',repaired_plans,repaired_java,repaired_jars)
            if any(not r['oracle_pass'] for r in new_rows) or any(v['verdict']!='not_reproduced' for v in new_outcomes.values()):raise IntegrityError('Fresh repaired runtime gate failed')
            page=business_dashboard.render(doc,explanation,[{'status':'accepted','proposal':spec}])
            repair_panel=report_visualizer.panel('Fresh repaired runtime verification',out/'repaired',new_sha,'repair')
            (out/'report.html').write_text(page.replace('</main>',repair_panel+'<p>Fresh M1 investigation, diagnosis and bounded restoration in this run. Healthy answer supplied; no arbitrary repair claim.</p></main>'))
            state.update(status='fresh_bounded_cycle_verified',outcomes={'broken':outcomes,'repaired':new_outcomes},repair_sha256=digest(restored.encode()),execution_mode='fresh_current_run')
            if identity(api('GET',f'/pulls/{number}'))!=(base,head):state['status']='stale'
            url='https://github.com/PrasathJaga/codex-wheel/actions/runs/'+os.environ['GITHUB_RUN_ID']
            text='<!-- codex-wheel-fresh-cycle-v1 -->\n### Codex Wheel — fresh bounded M1 cycle\n\n**Result: '+state['status']+'**\n\nBase `'+base+'` · Head `'+head+'`\n\nFresh investigation, diagnosis, exact healthy-source restoration and Java tests. '+str(state['worlds'])+' fresh runtime worlds, including no-fault controls. No arbitrary repair or automatic merge.\n\n[Run, HTML report and evidence]('+url+')'
            comments=api('GET',f'/issues/{number}/comments?per_page=100')
            matches=[c for c in comments if c['body'].startswith('<!-- codex-wheel-fresh-cycle-v1 -->') and c['user']['login']=='github-actions[bot]']
            if len(matches)>1:raise IntegrityError('Duplicate cycle comments')
            receipt=api('PATCH',f"/issues/comments/{matches[0]['id']}",{'body':text}) if matches else api('POST',f'/issues/{number}/comments',{'body':text})
            save(out,'publication.json',{'comment_id':receipt['id'],'status':state['status']})
            guard.verify('cycle_complete')
    except Exception as error:
        state.update(status='failed',error_type=type(error).__name__);raise
    finally:
        if ledger:state['new_model_calls']=len(ledger.attempts);state['usage']=[a.get('usage') for a in ledger.attempts]
        save(out,'cycle-summary.json',state)
        if runtime:runtime.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pr',type=int,required=True);p.add_argument('--expected',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.pr,a.expected,a.output)
