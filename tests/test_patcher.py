import copy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from wheel import patcher as p
from wheel.g6 import variants
from wheel.plan_guard import IntegrityError


def proposal():
    return {'old_text':'if (prior != null && request.amountMinorUnits() > 2500) {',
            'new_text':'if (prior != null) {','reason':'Reuse the existing effect for identical retry keys.'}


def test_only_reviewed_restoration_can_be_applied():
    policy=p.protocol();java,_=variants()
    assert p.apply_proposal(proposal(),java['M1'],policy)==java['base']
    for text in ('if (false) {','if (prior != null && request.amountMinorUnits() == 2500) {','return null;'):
        bad=proposal();bad['new_text']=text
        with pytest.raises(IntegrityError):p.apply_proposal(bad,java['M1'],policy)
    bad=proposal();bad['path']='wheel/verifier.py'
    with pytest.raises(IntegrityError):p.apply_proposal(bad,java['M1'],policy)
    with pytest.raises(IntegrityError):p.apply_proposal(proposal(),java['M1']+'// extra edit',policy)


def test_incomplete_or_non_tool_proposal_is_rejected():
    client=Mock()
    client.chat.completions.create.return_value=SimpleNamespace(choices=[SimpleNamespace(finish_reason='length')])
    with pytest.raises(IntegrityError):p.propose(client,{},[])
    assert client.chat.completions.create.call_count==1


def test_origin_hash_is_checked_before_parsing(tmp_path):
    file=tmp_path/'origin.zip';file.write_bytes(b'not an origin')
    with pytest.raises(IntegrityError):p.load_origin(file,p.protocol())


def test_recorded_proposal_stage_wiring_without_model_or_containers(tmp_path,monkeypatch):
    import json
    from wheel import intake
    java,python=variants()
    source_view={p.DOMAIN:{'base':java['base'],'candidate':java['M1']},
                 p.CLIENT:{'base':python['base'],'candidate':python['base']}}
    plans=[{'id':'plan-'+str(i),'mode':'selected' if i==0 else 'fixed',
            'source_hashes':{'java':{'base':'healthy','candidate':'broken'}}} for i in range(8)]
    def lock(protocol,expected,out):
        (out/'implementation-lock.json').write_text('{}')
        return expected,[]
    monkeypatch.setattr(p,'implementation_lock',lock)
    monkeypatch.setattr(intake,'source',lambda root,commit,name:(root/name).read_text())
    monkeypatch.setattr(p,'load_origin',lambda *a:(plans,source_view,[]))
    monkeypatch.setattr(p,'recorded_proposal',lambda *a:(proposal(),[{'usage':{'total_tokens':8482}}]))
    monkeypatch.setattr(p,'MetaAgent',lambda **kw:pytest.fail('Resume must not construct model client'))
    class Runtime:
        def __init__(self,*a):pass
        def prepare(self):return {'java':'image'}
        def probe(self):return {'probe':True}
        def close(self):pass
    monkeypatch.setattr(p,'DockerRuntime',Runtime)
    monkeypatch.setattr(p,'admitted_tests',lambda *a:None)
    def jars(java,scratch):
        result={}
        for name in java:
            path=scratch/(name+'.jar');path.write_bytes(name.encode());result[name]=path
        return result
    monkeypatch.setattr(p,'build_jars',jars)
    stages=[]
    def execute(plans,policy,runtime,jars,java,python,out,scratch,guard,manifest):
        assert policy['case']=='M1' and policy['trials']==3 and policy['caps']['worlds']==48
        stage=out.name;stages.append(stage)
        assert java['M1']==source_view[p.DOMAIN]['candidate'] if stage=='broken' else java['M1']==source_view[p.DOMAIN]['base']
        return [{} for _ in range(48)],{item['id']:{'verdict':'reproduced_regression' if stage=='broken' and item['mode']=='selected' else 'not_reproduced'} for item in plans}
    monkeypatch.setattr(p,'execute',execute)
    monkeypatch.setattr(p,'revision',lambda:'a'*40)
    output=tmp_path/'out';p.run('a'*40,tmp_path/'unused',output,tmp_path/'recorded')
    assert stages==['broken','repaired']
    assert json.loads((output/'summary.json').read_text())['new_model_requests']==0
