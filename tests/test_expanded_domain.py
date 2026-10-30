import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from wheel import expanded_domain as x
from wheel.investigator import SourceTools, ProposalError, InvestigatorAbstained, InvestigationInconclusive
from wheel.plan_guard import IntegrityError
from wheel.meta_agent import fingerprint
from wheel.repeatability import validate_pair


def test_protocol_admission_and_shared_domain():
    p=x.load_protocol(); views, admission, schema=x.admit(p)
    assert admission['provenance']==p['provenance']
    assert admission['source_hashes']['python']['base']==admission['source_hashes']['python']['candidate']
    assert schema['status']=='schema_unchanged'
    specs=x.fixed_specs(p)
    assert len(specs)==18 and len(specs)*6+12==p['caps']['worlds']
    assert all(s['amount_minor_units'] in x.allowed_amounts(p) for s in specs)
    assert 5500 in x.allowed_amounts(p)
    assert not any(s['amount_minor_units']==5500 for s in specs)
    mediator=SourceTools(views,x.DOMAIN,x.allowed_amounts(p))
    mediator.dispatch('read_diff',{})
    refs=[]
    for path,version in [(x.DOMAIN,'candidate'),(x.CLIENT,'base')]:
        mediator.dispatch('read_source',{'path':path,'version':version})
        lines=views[path][version].splitlines()
        line=next(i for i,t in enumerate(lines,1) if ('if (prior != null' if path==x.DOMAIN else 'key = str(uuid.uuid4())') in t)
        refs.append({'path':path,'version':version,'start_line':line,'end_line':line,'quote':lines[line-1]})
    proposal={'customer_message':'Please refund order ORD-SYN-TRIAL for USD 55.00.',
              'amount_minor_units':5500,'hypothesis':'Retry may commit twice.',
              'fault':{'action':'DROP_DOWNSTREAM_BEFORE_RESPONSE','min':5500,'max':5500},'source_refs':refs}
    mediator.validate(proposal)
    for amount in (0,10001,True,5500.0):
        invalid=copy.deepcopy(proposal);invalid['amount_minor_units']=amount
        with pytest.raises(ProposalError): mediator.validate(invalid)
    a=x.plan(p,views,proposal,'C2_budgeted',0)
    b=x.plan(p,views,proposal,'C4_range',0)
    assert a['seed']==b['seed'] and a['rule']==b['rule']
    assert a['seed']['sha256']==fingerprint(a['seed']['payload'])
    assert 'messages' not in a['seed']['payload']
    assert a['changed_side']=='java'


def test_tampered_registered_source_rejected():
    p=x.load_protocol();p['candidate_sha256']='0'*64
    with pytest.raises(IntegrityError): x.admit(p)


def response(name,args,finish='tool_calls'):
    message={'role':'assistant','tool_calls':[{'id':'call1','type':'function',
        'function':{'name':name,'arguments':json.dumps(args)}}]}
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish,
        message=SimpleNamespace(model_dump=lambda **_:message))])


def test_abstention_preserved_without_fallback(tmp_path):
    p=x.load_protocol();views,_,_=x.admit(p);client=Mock()
    client.chat.completions.create.return_value=response('abstain',{'reason':'No justified plan'})
    path=tmp_path/'trace.json'
    with pytest.raises(InvestigatorAbstained): x.investigate(client,views,p,path)
    assert json.loads(path.read_text())[0]['tool_results'][0]['name']=='abstain'
    assert client.chat.completions.create.call_count==1
    public=json.loads(client.chat.completions.create.call_args.kwargs['messages'][1]['content'])
    assert public['public_fixture']['allowed_integer_amount_range']=={'min':1,'max':10000}
    assert 'U1' not in json.dumps(public) and 'mutation' not in public


def test_six_turn_limit(tmp_path):
    p=x.load_protocol();views,_,_=x.admit(p);client=Mock()
    client.chat.completions.create.return_value=response('read_diff',{})
    with pytest.raises(InvestigationInconclusive): x.investigate(client,views,p,tmp_path/'trace.json')
    assert client.chat.completions.create.call_count==6


def test_new_case_java_identity_is_checked():
    p=x.load_protocol();views,_,_=x.admit(p)
    item=x.plan(p,views,x.fixed_specs(p)[0],'C2_budgeted',0)
    manifest={'plan_hash':'fixed','policy':x.POLICY,'images':{'java':'pinned'},'build_hashes':{'base':'basejar','U1':'candidatejar'}}
    def record(which):
        return {'world':which,'trial':0,'plan_hash':'fixed','policy':x.POLICY,'images':manifest['images'],
            'fixture_sha256':fingerprint(item['fixture']),'seed_sha256':fingerprint(item['seed']),
            'rule_sha256':fingerprint(item['rule']),'reset_empty':True,'restart_recovered':True,
            'java_sha256':item['source_hashes']['java'][which],
            'python_sha256':item['source_hashes']['python'][which],
            'jar_sha256':'basejar' if which=='base' else 'candidatejar'}
    a,b=record('base'),record('candidate');validate_pair(a,b,item,manifest)
    b['jar_sha256']='basejar'
    with pytest.raises(IntegrityError): validate_pair(a,b,item,manifest)
