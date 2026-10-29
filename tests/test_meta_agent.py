import copy
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wheel.meta_agent import MetaAgent, validate_intent, fingerprint
from wheel.experiment import child_env

AUTH = {'order_id': 'ORD-SYN-TRIAL', 'amount_minor_units': 2500}
ARGS = {**AUTH, 'currency': 'USD', 'refund_scope': 'full_order'}
def message(args=None):
    return {'role':'assistant','tool_calls':[{'id':'call_test','type':'function',
        'function':{'name':'issue_refund','arguments':json.dumps(ARGS if args is None else args)}}]}
class FakeClient:
    def __init__(self, output=None, error=None):
        self.chat=SimpleNamespace(completions=self); self.output=output; self.error=error; self.requests=[]
    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.error: raise self.error
        return SimpleNamespace(id='mock_response', model='mock_only', usage=None,
            choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(model_dump=lambda **kw:self.output))])

class MetaContractTests(unittest.TestCase):
    def test_valid_intent(self):
        self.assertEqual(validate_intent(message(), AUTH), ARGS)
    def test_reject_wrong_and_extra_arguments(self):
        for changes in [{'amount_minor_units':True}, {'amount_minor_units':2501},
                        {'order_id':'ORD-SYN-OTHER'}, {'currency':'EUR'},
                        {'refund_scope':'partial'}, {'max_attempts':3}, {'idempotency_key':'fixed'}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_intent(message({**ARGS, **changes}), AUTH)
    def test_reject_missing_multiple_and_wrong_tools(self):
        for calls in [[],message()['tool_calls']*2,[{'id':'x','type':'function','function':{'name':'other'}}]]:
            with self.assertRaises(ValueError): validate_intent({'role':'assistant','tool_calls':calls}, AUTH)
    def test_reject_malformed_duplicate_json(self):
        for raw in ['{', '[]', '{"order_id":"a","order_id":"b"}']:
            m=message();m['tool_calls'][0]['function']['arguments']=raw
            with self.assertRaises(ValueError): validate_intent(m,AUTH)
    def test_child_environment_excludes_credentials(self):
        with patch.dict(os.environ, {'MODEL_API_KEY':'test-secret','WHEEL_EVALUATOR_TOKEN':'oracle','OTHER_SECRET':'x'}):
            self.assertFalse(set(child_env()) & {'MODEL_API_KEY','WHEEL_EVALUATOR_TOKEN','OTHER_SECRET'})
    def test_missing_key(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(RuntimeError,'missing'):
            MetaAgent()
    def test_budget_and_transport_redaction(self):
        client=FakeClient({'role':'assistant','content':'mock only'})
        agent=MetaAgent(client)
        for _ in range(6): agent.generate([],False)
        with self.assertRaisesRegex(RuntimeError,'budget'): agent.generate([],False)
        self.assertEqual(len(client.requests),6)
        self.assertTrue(all(r['tool_choice']=='auto' for r in client.requests))
        agent=MetaAgent(FakeClient(error=RuntimeError('SECRET VALUE')))
        with self.assertRaises(RuntimeError) as error: agent.generate([],True)
        self.assertNotIn('SECRET',str(error.exception))
    def test_frozen_replay_and_tamper(self):
        client=FakeClient({'role':'assistant','content':'Mock confirmation'})
        agent=MetaAgent(client)
        payload={'messages':[message()], 'arguments':ARGS,'authorization':AUTH,'tool_call_id':'call_test'}
        agent.frozen['M1']={'payload':copy.deepcopy(payload),'sha256':fingerprint(payload)}
        receipt={'status':'committed'}
        agent.continue_world('M1',receipt)
        sent=client.requests[0]['messages']
        self.assertEqual(sent[0],payload['messages'][0])
        self.assertEqual(sent[-1]['tool_call_id'],'call_test')
        self.assertEqual(json.loads(sent[-1]['content']),receipt)
        agent.frozen['M1']['payload']['arguments']['amount_minor_units']=1
        with self.assertRaisesRegex(ValueError,'changed'): agent.intent('M1')
    def test_continuation_cannot_execute_more_tools(self):
        for output in [message(),{'role':'assistant','content':''}]:
            agent=MetaAgent(FakeClient(output)); payload={'messages':[],'tool_call_id':'id'}
            agent.frozen['M1']={'payload':payload,'sha256':fingerprint(payload)}
            with self.assertRaises(ValueError): agent.continue_world('M1',{})

if __name__=='__main__': unittest.main()
