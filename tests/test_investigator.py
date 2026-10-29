"""Offline investigator mediation tests: all responses here are fake."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from wheel.investigator import SourceTools, ProposalError, Investigator, InvestigationInconclusive

SOURCES={'producer.java':{'base':'dedup();\ncommit();\n','candidate':'if (amount > 2500) dedup();\ncommit();\n'},
         'client.py':{'base':'retry_same_key()\n','candidate':'retry_same_key()\n'}}
def proposal():
    return dict(customer_message='Refund ORD-SYN-TRIAL for USD 25.00',amount_minor_units=2500,
        fault={'action':'DROP_DOWNSTREAM_BEFORE_RESPONSE','min':2500,'max':2500},
        source_refs=[dict(path='producer.java',version='candidate',start_line=1,end_line=1,quote='if (amount > 2500) dedup();'),
                     dict(path='client.py',version='base',start_line=1,end_line=1,quote='retry_same_key()')],
        hypothesis='Ambiguous completion followed by retry may duplicate an effect.')
def read_all(m):
    m.dispatch('read_diff',{})
    m.dispatch('read_source',{'path':'producer.java','version':'candidate'})
    m.dispatch('read_source',{'path':'client.py','version':'base'})
def call(name,args,ident='test-call'):
    return dict(id=ident,type='function',function=dict(name=name,arguments=json.dumps(args)))
class ScriptedClient:
    def __init__(self,script):
        self.script=iter(script);self.requests=[];self.chat=SimpleNamespace(completions=self)
    def create(self,**kwargs):
        self.requests.append(copy.deepcopy(kwargs));calls=next(self.script)
        msg={'role':'assistant','tool_calls':calls}
        return SimpleNamespace(id='fake',model='fake-only',usage=None,
            choices=[SimpleNamespace(finish_reason='tool_calls',message=SimpleNamespace(model_dump=lambda **kw:msg))])

class InvestigatorTests(unittest.TestCase):
    def test_forbidden_tools_paths_and_oracle_names(self):
        m=SourceTools(SOURCES,'producer.java')
        for name in ['shell','read_ledger','get_secret','write_source']:
            with self.assertRaises(ProposalError): m.dispatch(name,{})
        for path in ['../producer.java','/etc/passwd','wheel/verifier.py','evaluator_only/labels.json','MODEL_API_KEY']:
            with self.assertRaises(ProposalError): m.dispatch('read_source',dict(path=path,version='base'))

    def test_proposal_requires_actual_reads_and_exact_spans(self):
        m=SourceTools(SOURCES,'producer.java')
        with self.assertRaises(ProposalError): m.dispatch('propose_experiment',proposal())
        read_all(m)
        for changes in [{'quote':'invented()'},{'start_line':True},{'end_line':100},{'version':'base'}]:
            p=proposal();p['source_refs'][0].update(changes)
            with self.assertRaises(ProposalError): m.dispatch('propose_experiment',p)
        self.assertEqual(m.dispatch('propose_experiment',proposal()),proposal())
        with self.assertRaises(ProposalError): m.dispatch('read_diff',{})

    def test_public_high_value_fixture_rejects_low_value_before_execution(self):
        m=SourceTools(SOURCES,'producer.java',allowed_amounts=(7500,));read_all(m)
        with self.assertRaises(ProposalError): m.dispatch('propose_experiment',proposal())
        p=proposal();p['amount_minor_units']=7500
        p['fault']={'action':'PASS_THROUGH','min':7500,'max':7500}
        # Eligibility enforces value, not the desired fault or regression result.
        self.assertEqual(m.dispatch('propose_experiment',p)['fault']['action'],'PASS_THROUGH')

    def test_model_cannot_set_oracle_or_unbounded_fault(self):
        for update in [{'expected_effect_count':2},{'amount_minor_units':True},
                       {'fault':{'action':'SHELL','min':1,'max':7500}},
                       {'fault':{'action':'PASS_THROUGH','min':1,'max':100000001}},
                       {'fault':{'action':'PASS_THROUGH','min':3000,'max':7500}}]:
            m=SourceTools(SOURCES,'producer.java');read_all(m);p=proposal();p.update(update)
            with self.assertRaises(ProposalError): m.dispatch('propose_experiment',p)

    def test_harmless_rule_is_not_rejected_to_force_a_regression(self):
        m=SourceTools(SOURCES,'producer.java');read_all(m);p=proposal()
        p['fault']['action']='PASS_THROUGH'
        self.assertEqual(m.dispatch('propose_experiment',p)['fault']['action'],'PASS_THROUGH')

    def test_real_loop_mediates_reads_then_accepts_and_logs_fake_identity(self):
        script=[[call('read_diff',{},'a'),call('read_source',{'path':'producer.java','version':'candidate'},'b'),
                 call('read_source',{'path':'client.py','version':'base'},'c')],
                [call('propose_experiment',proposal())]]
        with tempfile.TemporaryDirectory() as directory:
            client=ScriptedClient(script);agent=Investigator(client,Path(directory)/'trace.json')
            self.assertEqual(agent.investigate(SOURCES,'producer.java'),proposal())
            self.assertEqual(agent.calls,2)
            self.assertTrue(all(t['model']=='fake-only' for t in agent.traces))
            self.assertEqual([m['tool_call_id'] for m in client.requests[1]['messages'] if m['role']=='tool'],['a','b','c'])
            self.assertNotIn('oracle',json.dumps(agent.traces[0]['tool_results']))

    def test_bounded_invalid_plans_and_abstention_never_return_plan(self):
        for script in [[[call('propose_experiment',{})]]*6, [[call('abstain',{'reason':'insufficient source'})]]]:
            with tempfile.TemporaryDirectory() as directory:
                agent=Investigator(ScriptedClient(script),Path(directory)/'trace.json')
                with self.assertRaises(InvestigationInconclusive): agent.investigate(SOURCES,'producer.java')
                self.assertLessEqual(agent.calls,6)

if __name__=='__main__': unittest.main()
