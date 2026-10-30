import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from wheel import interface_followup as f
from wheel.expanded_domain import allowed_amounts
from wheel.investigator import TOOLS, SourceTools, ProposalError, InvestigatorAbstained, InvestigationInconclusive
from wheel.evaluation_model import RequestLimit
from wheel.meta_agent import MODEL


def views():return f.admit(f.original_protocol())[0]


def test_registered_change_is_prompt_only_and_limits_fixed():
    p=f.protocol()
    assert p['arms'][1]['developer_prompt'].startswith(p['arms'][0]['developer_prompt'])
    assert p['caps']['investigator_requests']==2*p['caps']['per_arm_requests']==12
    assert p['caps']['worlds']==2*2*3*2==24
    assert p['prior']['C2'].startswith('reuse_verified_historical')
    assert 'base' in p['arms'][1]['developer_prompt']
    assert 'minor units, not request counts' in p['arms'][1]['developer_prompt']


def test_real_failed_proposals_have_multiple_simultaneous_issues():
    traces=json.loads((Path(__file__).parent/'fixtures/interface_v1_rejections.json').read_text())
    audit=f.audit_proposals(traces,views(),range(1,10001))
    assert [x['amount_minor_units'] for x in audit]==[5500]*3
    assert [{i['code'] for i in a['issues']} for a in audit]==[
        {'fault_amount_bounds','quote_span_mismatch','missing_peer_base_citation'},
        {'quote_span_mismatch','missing_peer_base_citation'},
        {'missing_peer_base_citation'}]
    assert next(i for i in audit[-1]['issues'] if i['code']=='missing_peer_base_citation')['peer_base_candidate_bytes_equal'] is True


@pytest.mark.parametrize('arm_index',[0,1])
def test_prompt_proxy_preserves_tools_user_input_and_request_budget(tmp_path,arm_index):
    p=f.protocol();client=Mock();seen=[]
    def response(**request):
        seen.append(copy.deepcopy(request))
        message={'role':'assistant','tool_calls':[{'id':'read','type':'function','function':{'name':'read_diff','arguments':'{}'}}]}
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='tool_calls',message=SimpleNamespace(model_dump=lambda **kw:message))])
    client.chat.completions.create.side_effect=response
    with pytest.raises(InvestigationInconclusive):
        f.investigate(f.prompt_client(client,p['arms'][arm_index]['developer_prompt']),views(),f.original_protocol(),tmp_path/'trace.json')
    assert len(seen)==6
    assert all(r['messages'][0]['content']==p['arms'][arm_index]['developer_prompt'] and r['tools']==TOOLS for r in seen)
    assert all(r['model']==MODEL and r['max_completion_tokens']==2048 for r in seen)
    user=seen[0]['messages'][1]['content']
    assert '5500' not in user and 'prior' not in user and 'U1' not in user
    assert json.loads(user)['public_fixture']['allowed_integer_amount_range']=={'min':1,'max':10000}


def test_global_and_per_arm_caps_include_failed_requests(tmp_path):
    client=Mock();client.chat.completions.create.side_effect=RuntimeError('private body')
    ledger=f.FollowupLedger(client,tmp_path/'attempts.json')
    request={'model':MODEL,'messages':[{'role':'developer','content':'public'}],'tools':TOOLS,
             'tool_choice':'auto','max_completion_tokens':2048,'reasoning_effort':'low'}
    for arm in ('old_interface','clarified_interface'):
        for _ in range(6):
            with pytest.raises(RuntimeError):ledger.scoped('C4','investigator',arm).chat.completions.create(**request)
        with pytest.raises(RequestLimit):ledger.scoped('C4','investigator',arm).chat.completions.create(**request)
    assert len(ledger.attempts)==client.chat.completions.create.call_count==12
    assert 'private body' not in (tmp_path/'attempts.json').read_text()
    with pytest.raises(RequestLimit):ledger.scoped('C4','investigator','extra').chat.completions.create(**request)


def test_both_failed_outcomes_are_preserved_without_fallback(tmp_path,monkeypatch):
    p=f.protocol();ledger=SimpleNamespace(attempts=[],scoped=lambda *a:Mock())
    call=Mock(side_effect=[InvestigatorAbstained('no plan'),InvestigationInconclusive('invalid')])
    monkeypatch.setattr(f,'investigate',call)
    plans,selections=f.select(p,f.original_protocol(),views(),ledger,tmp_path)
    assert plans==[] and [s['status'] for s in selections]==['abstained','inconclusive']
    assert call.call_count==2 and len(json.loads((tmp_path/'selections.json').read_text()))==2


def test_validator_still_rejects_candidate_peer_label():
    view=views();m=SourceTools(view,f.DOMAIN,range(1,10001));m.dispatch('read_diff',{})
    refs=[]
    for path,version in ((f.DOMAIN,'candidate'),(f.CLIENT,'candidate')):
        m.dispatch('read_source',{'path':path,'version':version});line=54 if path==f.DOMAIN else 34
        refs.append({'path':path,'version':version,'start_line':line,'end_line':line,'quote':view[path][version].splitlines()[line-1]})
    proposal={'customer_message':'Synthetic refund','hypothesis':'Retry hypothesis','amount_minor_units':5500,
              'fault':{'action':'DROP_DOWNSTREAM_BEFORE_RESPONSE','min':5500,'max':5500},'source_refs':refs}
    with pytest.raises(ProposalError,match='unchanged peer'):m.validate(proposal)
    m.dispatch('read_source',{'path':f.CLIENT,'version':'base'});proposal['source_refs'][1]['version']='base'
    m.validate(proposal)


def test_both_arms_accept_same_valid_plan_without_changing_validator(tmp_path):
    p=f.protocol();view=views();counter=[]
    refs=[{'path':path,'version':version,'start_line':line,'end_line':line,'quote':view[path][version].splitlines()[line-1]}
          for path,version,line in ((f.DOMAIN,'candidate',54),(f.CLIENT,'base',34))]
    proposal={'customer_message':'Please refund ORD-SYN-TRIAL for USD 55.00.','hypothesis':'Retry may duplicate a committed effect.',
              'amount_minor_units':5500,'fault':{'action':'DROP_DOWNSTREAM_BEFORE_RESPONSE','min':5500,'max':5500},'source_refs':refs}
    def provider(**request):
        index=len(counter)%3;counter.append(copy.deepcopy(request))
        specs=[('read_diff',{})] if index==0 else [('read_source',{'path':f.DOMAIN,'version':'candidate'}),('read_source',{'path':f.CLIENT,'version':'base'})] if index==1 else [('propose_experiment',proposal)]
        message={'role':'assistant','tool_calls':[{'id':'call-'+str(i),'type':'function','function':{'name':name,'arguments':json.dumps(args)}} for i,(name,args) in enumerate(specs)]}
        response=SimpleNamespace(id='response-'+str(len(counter)),model=MODEL,
            usage=SimpleNamespace(model_dump=lambda:{'total_tokens':1}),
            choices=[SimpleNamespace(finish_reason='tool_calls',message=SimpleNamespace(model_dump=lambda **kw:message))],
            model_dump=lambda **kw:{'choices':[{'message':message}]})
        return response
    client=Mock();client.chat.completions.create.side_effect=provider
    ledger=f.FollowupLedger(client,tmp_path/'requests.json')
    plans,selections=f.select(p,f.original_protocol(),view,ledger,tmp_path)
    assert len(counter)==len(ledger.attempts)==6 and len(plans)==4
    assert [s['status'] for s in selections]==['accepted','accepted']
    assert plans[0]['seed']==plans[2]['seed'] and plans[0]['rule']==plans[2]['rule']
    assert all(item['changed_side']=='java' for item in plans)
    ledger.phase='worlds'
    with pytest.raises(RequestLimit):ledger.scoped('C4','investigator','old_interface').chat.completions.create(**counter[0])
    assert len(counter)==6
