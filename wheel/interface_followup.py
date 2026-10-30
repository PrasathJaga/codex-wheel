"""Registered prompt-clarity follow-up: one fresh old and clarified selection, same validator."""
import argparse
import copy
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import zipfile

from wheel.evaluation import implementation_lock, save
from wheel.evaluation_model import RequestLedger, RequestLimit
from wheel.expanded_domain import load_protocol as original_protocol, admit, investigate, plan, execute
from wheel.experiment import ROOT, DOMAIN, CLIENT, digest
from wheel.g6 import build_jars, revision
from wheel.intake import source
from wheel.investigator import strict_json, SourceTools, ProposalError, InvestigatorAbstained, InvestigationInconclusive
from wheel.isolation import DockerRuntime
from wheel.meta_agent import MetaAgent
from wheel.plan_guard import IntegrityError, PlanGuard
from wheel.repeatability import POLICY

PROTOCOL_SHA='988d82b8d3707a8681d4c7d9f8f93bc517a03c0fc2dc6badda730601b6a4ed69'


def protocol():
    path=ROOT/'evaluation/interface_followup_v2.json'
    if path.is_symlink() or digest(path.read_bytes())!=PROTOCOL_SHA:raise IntegrityError('Follow-up protocol mismatch')
    p=strict_json(path.read_text())
    for name,expected in p['protected_components'].items():
        path=ROOT/name
        if path.is_symlink() or digest(path.read_bytes())!=expected:raise IntegrityError('Protected component drift: '+name)
    return p


def audit_proposals(traces,views,allowed):
    """Reconstruct actual source reads; collect concurrent defects obscured by fail-fast validation."""
    reads=set();audit=[]
    for trace in traces:
        for call in trace['assistant'].get('tool_calls',[]):
            name=call['function']['name'];args=strict_json(call['function']['arguments'])
            if name=='read_source':reads.add((args['path'],args['version']))
            if name!='propose_experiment':continue
            issues=[];fault=args['fault'];amount=args['amount_minor_units']
            if type(amount) is not int or amount not in allowed:
                issues.append({'code':'amount_outside_domain','classification':'model_parameter_error'})
            if not (type(fault['min']) is int and type(fault['max']) is int and 1<=fault['min']<=amount<=fault['max']<=100000):
                issues.append({'code':'fault_amount_bounds','classification':'invalid_model_parameters_with_undocumented_units'})
            for ref in args['source_refs']:
                lines=views[ref['path']][ref['version']].splitlines()
                actual='\n'.join(lines[ref['start_line']-1:ref['end_line']])
                if ref['quote']!=actual:
                    issues.append({'code':'quote_span_mismatch','classification':'model_citation_error','path':ref['path'],
                                   'declared_lines':ref['end_line']-ref['start_line']+1,'quoted_lines':len(ref['quote'].splitlines())})
                if (ref['path'],ref['version']) not in reads:issues.append({'code':'unread_reference','classification':'model_tool_use_error'})
            cited={(r['path'],r['version']) for r in args['source_refs']}
            if not any(path!=DOMAIN and version=='base' for path,version in cited):
                issues.append({'code':'missing_peer_base_citation','classification':'interface_contract_not_explicit_in_prompt_or_tool_schema',
                               'peer_base_candidate_bytes_equal':views[CLIENT]['base']==views[CLIENT]['candidate']})
            audit.append({'turn':trace['turn'],'amount_minor_units':amount,'fault':fault,'issues':issues,
                          'recorded_rejection':next((r.get('result',{}).get('reason') for r in trace['tool_results'] if r['name']=='rejected'),None)})
    return audit


def prior_evidence(path,p,views):
    path=Path(path)
    if path.is_symlink() or path.stat().st_size>8*1024*1024 or digest(path.read_bytes())!=p['prior']['zip_sha256']:
        raise IntegrityError('Prior artifact mismatch')
    with zipfile.ZipFile(path) as z:
        if digest(z.read('locked-comparison.json'))!=p['prior']['plan_sha256']:raise IntegrityError('Prior plan mismatch')
        old=json.loads(z.read('locked-comparison.json'))
        if old['protocol_sha256']!=p['prior']['protocol_sha256']:raise IntegrityError('Prior protocol mismatch')
        if json.loads(z.read('source-snapshots.json'))!=views:raise IntegrityError('Case source changed')
        traces=json.loads(z.read('investigator-traces.json'));attempts=json.loads(z.read('request-attempts.json'))
        summary=json.loads(z.read('summary.json'))
        if attempts[0]['request']['messages'][0]['content']!=p['arms'][0]['developer_prompt']:
            raise IntegrityError('Control prompt differs from prior request')
        return {'methods':summary['methods'],'requests':summary['requests'],
                'provider_tokens':sum(u['total_tokens'] for u in summary['usage']),
                'source':'verified_historical_artifact_not_fresh_execution'},traces


class FollowupLedger(RequestLedger):
    def create(self,method,role,selection,**kwargs):
        if (method,role)!=('C4','investigator') or len(self.attempts)>=12:
            raise RequestLimit('Follow-up global request cap or role violation')
        return super().create(method,role,selection,**kwargs)


def prompt_client(client,prompt):
    """Intercept only developer text; unchanged loop, tools, validation, and provider configuration."""
    def create(**kwargs):
        request=copy.deepcopy(kwargs)
        if not request['messages'] or request['messages'][0]['role']!='developer':raise IntegrityError('Prompt role drift')
        request['messages'][0]['content']=prompt
        return client.chat.completions.create(**request)
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def select(p,old,views,ledger,out):
    selections=[];plans=[]
    for arm in p['arms']:
        entry={'id':arm['id'],'status':'analysis_error','requests':0}
        before=len(ledger.attempts)
        try:
            proposal=investigate(prompt_client(ledger.scoped('C4','investigator',arm['id']),arm['developer_prompt']),
                                 views,old,out/(arm['id']+'-traces.json'))
            entry.update(status='accepted',proposal=proposal)
            plans.extend([plan(old,views,proposal,arm['id'],0),plan(old,views,proposal,arm['id'],1,True)])
        except InvestigatorAbstained:entry['status']='abstained'
        except InvestigationInconclusive as error:entry.update(status='inconclusive',error_type=type(error).__name__)
        except Exception as error:entry.update(status='analysis_error',error_type=type(error).__name__)
        entry['requests']=len(ledger.attempts)-before
        if entry['requests']>p['caps']['per_arm_requests']:raise IntegrityError('Arm request cap exceeded')
        selections.append(entry);save(out,'selections.json',selections)
    return plans,selections


def run(expected,prior,output):
    p=protocol();old=original_protocol();out=Path(output).absolute();out.mkdir(exist_ok=False)
    started=time.monotonic();runtime=None
    try:
        commit,paths=implementation_lock({'core_budget':p['caps']},expected,out)
        lock=json.loads((out/'implementation-lock.json').read_text());lock['protocol_sha256']=PROTOCOL_SHA
        for name in ('evaluation/interface_followup_v2.json','.github/workflows/interface-followup.yml'):
            path=ROOT/name
            if path.is_symlink() or source(ROOT,commit,name).encode()!=path.read_bytes():raise IntegrityError('Uncommitted follow-up input')
            paths.append(path);lock['source_hashes'][name]=digest(path.read_bytes())
        save(out,'implementation-lock.json',lock)
        guard=PlanGuard(out/'implementation-lock.json',(out/'implementation-lock.json').read_bytes(),paths)
        views,admission,schema=admit(old);history,traces=prior_evidence(prior,p,views)
        audit=audit_proposals(traces,views,range(1,10001))
        save(out,'prior-review.json',{'prior':p['prior'],'historical_result':history,'proposal_audit':audit})
        save(out,'source-snapshots.json',views);save(out,'source-admission.json',admission)
        save(out,'schema-results.json',schema);save(out,'protocol.json',p)
        client=MetaAgent(max_calls=1).client
        ledger=FollowupLedger(client,out/'request-attempts.json');ledger.persist()
        with tempfile.TemporaryDirectory(prefix='wheel-interface-') as directory:
            scratch=Path(directory);runtime=DockerRuntime(ROOT,scratch)
            images=runtime.prepare();probes=runtime.probe()
            java={'base':views[DOMAIN]['base'],'U1':views[DOMAIN]['candidate']};python={'base':views[CLIENT]['base']}
            jars=build_jars(java,scratch)
            selected_at=time.monotonic();plans,selections=select(p,old,views,ledger,out)
            selection_seconds=time.monotonic()-selected_at
            frozen={'commit':commit,'protocol_sha256':PROTOCOL_SHA,'plans':plans,'selections':selections,'images':images,
                    'build_hashes':{k:digest(v.read_bytes()) for k,v in jars.items()},'prior_artifact_sha256':p['prior']['zip_sha256']}
            save(out,'locked-comparison.json',frozen)
            manifest={**frozen,'policy':POLICY,'plan_hash':digest((out/'locked-comparison.json').read_bytes())}
            ledger.phase='worlds'
            for path in [*out.iterdir(),*jars.values()]:guard.bind(path,path.read_bytes())
            guard.verify('both_arms_frozen_before_any_world')
            save(out,'results.json',[]);save(out,'outcomes.json',{})
            records,outcomes=execute(plans,{'case':'U1','trials':3,'caps':{'worlds':24}},runtime,jars,java,python,out,scratch,guard,manifest)
            methods={}
            for entry in selections:
                group=[x for x in plans if x['method']==entry['id']];verdicts=[outcomes[x['id']]['verdict'] for x in group]
                status=next((s for s in ('reproduced_regression','analysis_error','inconclusive') if s in verdicts),
                            'not_reproduced' if verdicts else entry['status'])
                methods[entry['id']]={'selection_status':entry['status'],'status':status,'plans':len(group),
                    'worlds':sum(r['method']==entry['id'] for r in records),'requests':entry['requests']}
            if len(records)>24 or len(ledger.attempts)>12 or revision()!=commit:raise IntegrityError('Follow-up budget/revision drift')
            for path in out.iterdir():guard.bind(path,path.read_bytes())
            guard.publish(out/'summary.json',{'status':'evaluated','commit':commit,'methods':methods,
                'historical_v1':history,'requests':len(ledger.attempts),'worlds':len(records),
                'usage':[a.get('usage') for a in ledger.attempts],'confinement':probes,
                'selection_seconds':selection_seconds,'wall_seconds':time.monotonic()-started,
                'numeric_usd_cost':None,'limits':p['limitations'],'runtime_binary_closure_exported':False})
            errors=any(x['status']=='analysis_error' for x in selections)
            save(out,'run-status.json',{'status':'completed_with_errors' if errors else 'completed','commit':commit})
            if errors:raise RuntimeError('Selection errors preserved')
    except BaseException as error:
        if not (out/'run-status.json').exists():save(out,'run-status.json',{'status':'analysis_error','error_type':type(error).__name__})
        raise
    finally:
        if runtime:runtime.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-implementation-commit',required=True)
    parser.add_argument('--prior',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'evidence-interface-v2')
    a=parser.parse_args();run(a.expected_implementation_commit,a.prior,a.output)
