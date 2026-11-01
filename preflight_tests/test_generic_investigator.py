import base64
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from preflight.generic_investigator import prepare, selection, diagnosis, implementation_sha256, run_investigation, evidence_packet
from preflight.executor_smoke import pack
from preflight.petclinic_adapter import digest, AdmissionError
from preflight.project_discovery import discover_pair
from preflight_tests.test_http_experiment import inputs
from preflight_tests.test_service_executor import service_config


def context():
    baseline = pack({'pyproject.toml': '[project]\nname="unit"', 'api.py': 'answer = 4\n'})
    candidate = pack({'pyproject.toml': '[project]\nname="unit"', 'api.py': 'answer = 5\n'})
    source = {'baseline_sha256': hashlib.sha256(baseline).hexdigest(), 'candidate_sha256': hashlib.sha256(candidate).hexdigest(), 'baseline_root':'source', 'candidate_root':'source'}
    discovery = discover_pair(baseline,candidate,source['baseline_sha256'],source['candidate_sha256'],'source','source')
    manifest, _, lifecycle = service_config(); manifest['discovery_sha256'] = digest(discovery)
    lifecycle['manifest_sha256'] = digest(manifest)
    _, _, _, bundle = inputs()
    interface, contract = bundle['interface'], bundle['contract']
    interface['manifest_sha256'] = contract['manifest_sha256'] = digest(manifest)
    policy = {'schema':'wheel-generic-investigation-policy-v1','attempt_id':'unit_attempt',
              'implementation_sha256':implementation_sha256(),'source_sha256':digest(source),
              'lifecycle_policy_sha256':digest(lifecycle),'interface_sha256':digest(interface),'contract_sha256':digest(contract),
              'source_paths':['api.py'],'paid_execution_enabled':False}
    return baseline,candidate,source,manifest,lifecycle,interface,contract,policy


def proposed(packet):
    return {'status':'propose','hypothesis':'The value may violate the approved expectation.',
            'source_refs':[{'side':s,'path':'api.py','line_start':1,'line_end':1} for s in ('baseline','candidate')],
            'plan':{'schema':'wheel-http-experiment-v1','interface_sha256':digest(packet['interface']),
                    'contract_sha256':digest(packet['contract']),'actions':[{'operation':'read_value','body':None}]}}


class FakeGateway:
    transport = 'test_double'
    def __init__(self, response=None, bad_diagnosis=False): self.calls=0; self.response=response; self.bad_diagnosis=bad_diagnosis
    def call(self, phase, prompt, packet):
        self.calls+=1
        if phase=='selection': return self.response or proposed(packet)
        return {'summary':'Recorded outcome remains the verifier result.',
                'source_refs':[{'side':'baseline','path':'api.py','line_start':1,'line_end':1}],
                'evidence_refs':['invented' if self.bad_diagnosis else next(iter(packet['evidence']))],
                'limitations':['Test double, not actual model ability.']}


def execution():
    raw=b'{"value":5}'
    return {'status':'confirmed_contract_violation','worlds':[{'side':'candidate','trial':1,
            'experiment':{'events':[{'action':{'operation':'read_value','body':None},'failures':['json_equality_0'],
            'response':{'status':200,'body_base64':base64.b64encode(raw).decode(),'body_sha256':hashlib.sha256(raw).hexdigest()}}]}}]}


class GenericInvestigatorTests(unittest.TestCase):
    def test_complete_schema_and_source_diff_without_labels_or_repair(self):
        args=context(); packet,_=prepare(*args)
        self.assertIn('answer = 4',packet['diffs']['api.py'])
        self.assertEqual(packet['plan_tool_schema']['properties']['actions']['items']['oneOf'][0]['required'],['operation','body'])
        self.assertNotIn('expected_label',json.dumps(packet))
        self.assertNotIn('repair',packet)
        args[-1]['implementation_sha256']='0'*64
        with self.assertRaises(AdmissionError): prepare(*args)

    def test_strict_selection_rejects_old_aliases_and_unresolved_source(self):
        args=context(); packet,sources=prepare(*args)
        good=proposed(packet)
        selection(good,packet,args[3],args[4],sources,args[5],args[6])
        for changed in [lambda v:v['plan']['actions'][0].update(ref='anything'),
                        lambda v:v['source_refs'][0].update(path='not-admitted.py')]:
            value=copy.deepcopy(good);changed(value)
            with self.assertRaises(AdmissionError): selection(value,packet,args[3],args[4],sources,args[5],args[6])

    def test_invalid_baseline_spends_no_requests_and_claim_cannot_repeat(self):
        args=context(); gateway=FakeGateway()
        with tempfile.TemporaryDirectory() as temp, patch('preflight.generic_investigator.run_service_pair',return_value={'status':'baseline_invalid'}):
            result=run_investigation(*args,Path(temp)/'out',Path(temp)/'claims',lambda *a:gateway)
            self.assertEqual(result['status'],'baseline_invalid');self.assertEqual(gateway.calls,0)
            with self.assertRaises(FileExistsError): run_investigation(*args,Path(temp)/'other',Path(temp)/'claims',lambda *a:gateway)

    def test_abstention_and_rejection_do_not_trigger_experiment_or_diagnosis(self):
        for response in [{'status':'abstain','reason':'Insufficient source.'},{'status':'propose','wrong':'shape'}]:
            args=context(); gateway=FakeGateway(response)
            with tempfile.TemporaryDirectory() as temp, patch('preflight.generic_investigator.run_service_pair',return_value={'status':'service_lifecycle_passed'}) as runner:
                result=run_investigation(*args,Path(temp)/'out',Path(temp)/'claims',lambda *a:gateway)
                self.assertEqual(result['status'],'inconclusive');self.assertEqual(gateway.calls,1);self.assertEqual(runner.call_count,1)

    def test_diagnosis_cannot_override_checker_and_rejected_citations_preserved(self):
        for invalid in (False,True):
            args=context(); gateway=FakeGateway(bad_diagnosis=invalid)
            with tempfile.TemporaryDirectory() as temp, patch('preflight.generic_investigator.run_service_pair',side_effect=[{'status':'service_lifecycle_passed'},execution()]):
                result=run_investigation(*args,Path(temp)/'out',Path(temp)/'claims',lambda *a:gateway)
                self.assertEqual(result['status'],'confirmed_contract_violation');self.assertEqual(gateway.calls,2)
                self.assertEqual(result['diagnosis_status'],'rejected' if invalid else 'references_validated_not_independent_causal_proof')
                self.assertEqual(result['paid_requests_attempted'],0)

    def test_paid_execution_disabled_before_any_runtime(self):
        args=context()
        with tempfile.TemporaryDirectory() as temp, patch('preflight.generic_investigator.run_service_pair') as runner:
            with self.assertRaises(AdmissionError): run_investigation(*args,Path(temp)/'out',Path(temp)/'claims',lambda *a:FakeGateway(),transport='meta')
            runner.assert_not_called()

    def test_response_excerpt_marks_truncation(self):
        result=execution(); response=result['worlds'][0]['experiment']['events'][0]['response']
        response['body_base64']=base64.b64encode(b'x'*600).decode()
        evidence=evidence_packet(result)
        value=next(iter(evidence.values()));self.assertTrue(value['excerpt_truncated']);self.assertEqual(len(value['body_excerpt']),512)


if __name__=='__main__': unittest.main()
