import base64
import copy
import json
import unittest
from unittest.mock import patch

from preflight.http_experiment import admit_experiment, tool_schema, assess, execute
from preflight.petclinic_adapter import AdmissionError, digest
from preflight_tests.test_execution_manifest import configured


def inputs():
    manifest, _ = configured()
    policy = {'reviewed': 'lifecycle-policy-placeholder-for-interface-unit-test'}
    refs = [{'side': s, 'path':'api.py', 'line_start':1, 'line_end':1} for s in ('baseline','candidate')]
    interface = {'schema':'wheel-http-interface-v1','manifest_sha256':digest(manifest),
                 'operations':[{'id':'read_value','method':'GET','path':'/value','body_schema':None,'source_refs':refs},
                               {'id':'set_value','method':'POST','path':'/value',
                                'body_schema':{'type':'object','additionalProperties':False,'required':['value'],
                                               'properties':{'value':{'type':'integer','minimum':0,'maximum':10}}},'source_refs':refs}]}
    contract = {'schema':'wheel-http-contract-v1','manifest_sha256':digest(manifest),
                'provenance':{'kind':'developer_declared','reference':'reviewed example expectation'},
                'checks':[{'operation':op,'statuses':[200],'json_equals':[{'path':['value'],'value':4}]} for op in ('read_value','set_value')]}
    plan = {'schema':'wheel-http-experiment-v1','interface_sha256':digest(interface),'contract_sha256':digest(contract),
            'actions':[{'operation':'read_value','body':None}]}
    bundle = {'interface':interface,'contract':contract,'plan':plan,'policy':{}}
    freeze(bundle, policy)
    sources = {side:{'api.py':b'example source line\n'} for side in ('baseline','candidate')}
    return manifest, policy, sources, bundle


def freeze(bundle, lifecycle):
    bundle['plan']['interface_sha256'] = digest(bundle['interface'])
    bundle['plan']['contract_sha256'] = digest(bundle['contract'])
    bundle['policy'] = {'schema':'wheel-http-experiment-policy-v1','lifecycle_policy_sha256':digest(lifecycle),
                        **{k+'_sha256':digest(bundle[k]) for k in ('interface','contract','plan')}}


def response(value, status=200):
    return {'status':status,'body_base64':base64.b64encode(json.dumps(value).encode()).decode()}


class HttpExperimentTests(unittest.TestCase):
    def test_complete_schema_matches_admitted_example_for_all_action_fields(self):
        m,p,s,b = inputs()
        admitted = admit_experiment(m,p,s,b)
        schema = tool_schema(b['interface'],b['contract'])
        self.assertEqual(schema['required'], ['schema','interface_sha256','contract_sha256','actions'])
        action_schema = schema['properties']['actions']['items']['oneOf'][0]
        self.assertEqual(set(action_schema['properties']), {'operation','body'})
        admitted['plan']['actions'].clear()
        self.assertEqual(len(b['plan']['actions']),1)

    def test_wrong_action_shapes_are_rejected_without_alias_normalization(self):
        for action in [{'op':'GET','ref':'/value'}, {'operation':'read_value','reference':'/value'},
                       {'operation':'read_value','body':None,'url':'https://outside'}]:
            m,p,s,b = inputs(); b['plan']['actions']=[action]; freeze(b,p)
            with self.assertRaises(AdmissionError): admit_experiment(m,p,s,b)

    def test_policy_drift_and_unknown_source_lines_rejected(self):
        m,p,s,b = inputs(); b['plan']['actions'].append({'operation':'read_value','body':None})
        with self.assertRaisesRegex(AdmissionError,'trusted frozen policy'): admit_experiment(m,p,s,b)
        m,p,s,b = inputs(); b['interface']['operations'][0]['source_refs'][0]['line_end']=2; freeze(b,p)
        with self.assertRaisesRegex(AdmissionError,'out of range'): admit_experiment(m,p,s,b)

    def test_unapproved_url_body_and_sql_like_fields_rejected(self):
        for change in [lambda b:b['interface']['operations'][0].update(path='//outside'),
                       lambda b:b['interface']['operations'][0].update(path='/a?url=outside'),
                       lambda b:b['interface']['operations'][0].update(headers={'Authorization':'key'}),
                       lambda b:b['plan'].update(sql='SELECT 1'),
                       lambda b:b['plan']['actions'][0].update(body={'value':3})]:
            m,p,s,b=inputs(); change(b); freeze(b,p)
            with self.assertRaises(AdmissionError): admit_experiment(m,p,s,b)

    def test_typed_body_limits_and_missing_expectation(self):
        for value in [True,11,-1,'4']:
            m,p,s,b=inputs(); b['plan']['actions']=[{'operation':'set_value','body':{'value':value}}]; freeze(b,p)
            with self.assertRaises(AdmissionError): admit_experiment(m,p,s,b)
        m,p,s,b=inputs(); b['contract']['checks']=b['contract']['checks'][1:]; freeze(b,p)
        with self.assertRaisesRegex(AdmissionError,'missing expectation'): admit_experiment(m,p,s,b)

    def test_independent_equality_does_not_treat_true_as_one_or_missing_as_null(self):
        check={'statuses':[200],'json_equals':[{'path':['value'],'value':1}]}
        self.assertTrue(assess(response({'value':True}),check))
        self.assertFalse(assess(response({'value':1}),check))
        check['json_equals'][0]['value']=None
        self.assertTrue(assess(response({}),check))
        self.assertFalse(assess(response({'value':None}),check))
        self.assertEqual(assess(response({},500),check),['unexpected_http_status'])

    def test_transport_error_is_not_business_violation_and_prior_events_remain(self):
        _,_,_,b=inputs(); b['plan']['actions'] *= 2
        with patch('preflight.http_experiment.request',side_effect=[response({'value':5}),{'error':'deadline'}]):
            result=execute(b,'172.20.0.2',8080,10)
        self.assertEqual(result['status'],'execution_error')
        self.assertEqual(len(result['events']),2)
        self.assertEqual(result['events'][0]['failures'],['json_equality_0'])

    def test_actual_response_drives_verdict_not_model_prose(self):
        _,_,_,b=inputs()
        with patch('preflight.http_experiment.request',return_value=response({'value':5})):
            result=execute(b,'172.20.0.2',8080,10)
        self.assertEqual(result['status'],'contract_violated')
        self.assertEqual(result['plan_sha256'],digest(b['plan']))


if __name__=='__main__': unittest.main()
