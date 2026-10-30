import copy
import hashlib
import json
import pytest
from wheel import report_visualizer as v
from wheel.meta_agent import fingerprint
from wheel.plan_guard import IntegrityError


def evidence(tmp_path):
    p={'id':'C4-example-selected','case':'M1','mode':'selected','changed_side':'java',
       'fixture':{'order_id':'ORD-SYN-TRIAL','amount_minor_units':2500},
       'rule':{'action':'DROP_DOWNSTREAM_BEFORE_RESPONSE','min':2500,'max':2500},'seed':{'same':'seed'},
       'source_hashes':{'java':{'base':'healthy','candidate':'broken'},'python':{'base':'fixed','candidate':'fixed'}}}
    f={'commit':'a'*40,'plans':[p],'images':{'java':'image'},'build_hashes':{'base':'jar0','M1':'jar1'}}
    raw=json.dumps(f).encode();(tmp_path/'locked-comparison.json').write_bytes(raw);sha=hashlib.sha256(raw).hexdigest()
    rows=[]
    for trial in range(3):
        for side in ('base','candidate'):
            effects=[{'effect_id':f'{side}-{trial}-{i}','order_id':'ORD-SYN-TRIAL','amount_minor_units':2500,'currency':'USD','refund_scope':'full_order','idempotency_key_sha256':'key','committed_at':'2026-10-30'} for i in range(1 if side=='base' else 2)]
            events=[{'upstream_status':200,'action':'DROP_DOWNSTREAM_BEFORE_RESPONSE' if i==0 else 'PASS_THROUGH',
                    'key_sha256':'key','upstream_body':{'refund_effect_id':effects[min(i,len(effects)-1)]['effect_id']},
                    'commit_evidence':{'effect_id':effects[min(i,len(effects)-1)]['effect_id'],'rows_before_downstream_action':min(i+1,len(effects))}} for i in range(2)]
            label=f'example-{trial}-{side}'
            row={'plan_id':p['id'],'case':'M1','world':side,'trial':trial,'status':'completed','oracle_pass':side=='base',
                 'plan_hash':sha,'fixture_sha256':fingerprint(p['fixture']),'rule_sha256':fingerprint(p['rule']),
                 'seed_sha256':fingerprint(p['seed']),'policy':v.POLICY,'images':f['images'],'reset_empty':True,
                 'restart_recovered':True,'java_sha256':p['source_hashes']['java'][side],'python_sha256':'fixed',
                 'jar_sha256':'jar0' if side=='base' else 'jar1','label':label,'effects':effects,'events':events,
                 'transport_errors':['ReadError'],'model_reply':{'content':'<script>alert("bad")</script>'}}
            rows.append(row)
            (tmp_path/(label+'.tsv')).write_text(''.join('\t'.join([e['effect_id'],e['order_id'],str(e['amount_minor_units']),e['currency'],e['refund_scope'],e['idempotency_key_sha256'],e['committed_at']])+'\n' for e in effects))
    (tmp_path/'results.json').write_text(json.dumps(rows))
    return sha,rows


def test_report_recomputes_verdict_and_escapes_model_text(tmp_path):
    sha,rows=evidence(tmp_path)
    frozen,groups=v.inspect(tmp_path,sha)
    assert groups[0][2]['verdict']=='reproduced_regression'
    report=v.render(tmp_path,sha)
    assert '<script>' not in report and '&lt;script&gt;' in report
    assert 'Committed USD 50.00' in report and 'Recorded genuine Meta continuation' in report


def test_changed_oracle_or_ledger_is_rejected(tmp_path):
    sha,rows=evidence(tmp_path)
    rows[0]['oracle_pass']=False;(tmp_path/'results.json').write_text(json.dumps(rows))
    with pytest.raises(IntegrityError):v.inspect(tmp_path,sha)
    rows[0]['oracle_pass']=True;(tmp_path/'results.json').write_text(json.dumps(rows))
    (tmp_path/'example-0-base.tsv').write_text('forged')
    with pytest.raises(IntegrityError):v.inspect(tmp_path,sha)


def test_wrong_plan_root_and_path_traversal_rejected(tmp_path):
    sha,rows=evidence(tmp_path)
    with pytest.raises(IntegrityError):v.inspect(tmp_path,'0'*64)
    rows[0]['label']='../outside';(tmp_path/'results.json').write_text(json.dumps(rows))
    with pytest.raises(IntegrityError):v.inspect(tmp_path,sha)
