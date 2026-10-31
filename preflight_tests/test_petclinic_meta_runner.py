import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from preflight import petclinic_meta_runner as runner
from preflight.petclinic_adapter import AdmissionError, digest
from preflight.petclinic_world import child_environment

ROOT = Path(__file__).resolve().parents[1]


class FakeResponse:
    def __init__(self, raw):
        self.raw = raw
    def model_dump(self, **kwargs):
        return self.raw


class FakeClient:
    def __init__(self, values):
        self.values, self.requests = list(values), []
        self.chat = SimpleNamespace(completions=self)
    def create(self, **request):
        self.requests.append(request)
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        if isinstance(value, FakeResponse):
            return value
        return FakeResponse({'id': 'unit-only', 'model': 'muse-spark-1.3',
                             'usage': {'prompt_tokens': 10, 'completion_tokens': 10},
                             'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': json.dumps(value)}}]})


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.protocol = json.loads((ROOT / 'evaluation/petclinic_transfer_protocol_v2.json').read_text())
        self.controls = json.loads((ROOT / 'evaluation/petclinic_healthy_plans_v1.json').read_text())
        path = next(iter(json.loads((ROOT / 'evaluation/petclinic_transfer_protocol_v1.json').read_text())['frozen_components']))
        self.path = 'unit/source.java'
        self.payload = {'baseline_sources': {self.path: '1: class A {}\n2: // baseline'},
                        'candidate_sources': {self.path: '1: class A {}\n2: // changed'}, 'diff': 'unit only'}
        self.refs = [{'side': side, 'path': self.path, 'line_start': 1, 'line_end': 1} for side in ('baseline','candidate')]
        self.proposal = {'status': 'propose', 'hypothesis': 'Unit-test-only hypothesis', 'source_refs': self.refs,
                         'plan': self.controls[0]['plan']}
        self.diagnosis = {'summary': 'Unit-test-only interpretation', 'source_refs': self.refs,
                          'evidence_refs': ['world-4-event-1'], 'limitations': 'Simulated callback, not live evidence'}
        self.prompts = json.loads((ROOT / 'evaluation/petclinic_transfer_prompts_v2.json').read_text())

    def world(self, side, frozen, candidate='contract_violated'):
        return {'side': side, 'plan_sha256': frozen['sha256'], 'seed_sha256': 'b'*64,
                'status': candidate if side == 'candidate' else 'contract_satisfied',
                'events': [{'status': 204, 'fixture': 'unit-test-only', 'committed_state': {'visits': []}}]}

    def run_method(self, values, executor=None, method='wheel_meta'):
        with tempfile.TemporaryDirectory() as directory:
            client = FakeClient(values)
            gateway = runner.MetaGateway(client, directory, self.protocol, method, transport='test_double')
            result = runner.run_meta_method(self.protocol, self.payload, self.prompts, self.controls,
                                             gateway, executor or self.world, directory)
            files = {p.name: json.loads(p.read_text()) for p in Path(directory).glob('*.json')}
            return result, client, files

    def test_valid_selection_repeats_and_diagnosis_are_separate(self):
        result, client, files = self.run_method([self.proposal, self.diagnosis])
        self.assertEqual(result['status'], 'confirmed_violation')
        self.assertEqual(result['worlds_attempted'], 10)
        self.assertEqual(result['model_requests'], 2)
        self.assertEqual(result['paid_requests'], 0)
        self.assertIn('resolved_evidence', files['diagnosis-admission.json'])
        self.assertEqual([r['max_completion_tokens'] for r in client.requests], [12000, 8000])

    def test_diagnosis_cannot_upgrade_or_erase_verifier_result(self):
        invalid = {**self.diagnosis, 'evidence_refs': ['invented-event']}
        result, _, _ = self.run_method([self.proposal, invalid])
        self.assertEqual(result['status'], 'confirmed_violation')
        self.assertEqual(result['diagnosis_status'], 'rejected_or_error')
        result, _, _ = self.run_method([self.proposal, self.diagnosis], lambda s,p: self.world(s,p,'contract_satisfied'))
        self.assertEqual(result['status'], 'no_violation_observed')

    def test_baseline_failure_stops_before_any_model_call(self):
        result, client, _ = self.run_method([], lambda s,p: {**self.world(s,p), 'status': 'contract_violated'})
        self.assertEqual(result['status'], 'baseline_invalid')
        self.assertEqual(client.requests, [])

    def test_invalid_citation_and_abstention_preserved(self):
        invalid = copy.deepcopy(self.proposal)
        invalid['source_refs'][0]['line_end'] = 99
        result, client, files = self.run_method([invalid])
        self.assertEqual(result['status'], 'inconclusive')
        self.assertEqual(result['worlds_attempted'], 2)
        self.assertIn('response', files['selection-request.json'])
        result, _, _ = self.run_method([{'status': 'abstain', 'reason': 'No supported hypothesis'}])
        self.assertEqual(result['reason'], 'model_abstained')

    def test_provider_error_has_no_retry_or_exception_secret(self):
        error = RuntimeError('PRIVATE-API-KEY-IN-EXCEPTION')
        result, client, files = self.run_method([error])
        self.assertEqual(result['status'], 'execution_error')
        self.assertEqual(len(client.requests), 1)
        self.assertNotIn('PRIVATE-API-KEY', json.dumps(files))

    def test_truncation_and_duplicate_json_are_not_repaired(self):
        for raw in ('{"status":"propose"', '{"status":"abstain","status":"propose"}'):
            response = FakeResponse({'id':'unit','model':'muse-spark-1.3','choices':[{'finish_reason':'stop','message':{'role':'assistant','content':raw}}]})
            result, client, files = self.run_method([response])
            self.assertEqual(result['status'], 'inconclusive')
            self.assertEqual(len(client.requests), 1)
            self.assertEqual(files['selection-request.json']['response']['choices'][0]['message']['content'], raw)

    def test_mismatched_seed_and_inconsistent_results_cannot_confirm(self):
        result, _, _ = self.run_method([self.proposal,self.diagnosis], lambda s,p: {**self.world(s,p),'seed_sha256':('c' if s=='candidate' else 'b')*64})
        self.assertEqual(result['status'], 'inconclusive')
        ordinal = [0]
        def alternating(side, frozen):
            if side == 'candidate': ordinal[0] += 1
            return self.world(side, frozen, 'contract_violated' if ordinal[0] % 2 else 'contract_satisfied')
        result, _, _ = self.run_method([self.proposal,self.diagnosis], alternating)
        self.assertEqual(result['status'], 'inconclusive')

    def test_phase_receipt_prevents_resampling_even_with_new_gateway(self):
        with tempfile.TemporaryDirectory() as directory:
            client = FakeClient([self.proposal])
            gateway = runner.MetaGateway(client,directory,self.protocol,'simple_meta',transport='test_double')
            gateway.call('selection','unit',self.payload)
            fresh = runner.MetaGateway(client,directory,self.protocol,'simple_meta',transport='test_double')
            with self.assertRaises(FileExistsError): fresh.call('selection','unit',self.payload)
            with self.assertRaises(AdmissionError): gateway.call('diagnosis','unit',self.payload)
            self.assertEqual(len(client.requests),1)

    def test_world_budget_counts_before_executor(self):
        with tempfile.TemporaryDirectory() as directory:
            budget = runner.WorldBudget(self.world,1,directory)
            budget.run('baseline',self.controls[0])
            with self.assertRaises(AdmissionError): budget.run('candidate',self.controls[0])
            self.assertEqual(len(budget.worlds),1)

    def test_conventional_first_discovery_repeated_with_no_model(self):
        packet = {'case_input_sha256':'d'*64,'preparation':{'kind':'AI_assisted','author':'unit only','provenance_sha256':'e'*64},'experiments':[self.proposal]}
        with tempfile.TemporaryDirectory() as directory:
            result = runner.run_conventional(self.protocol,self.payload,self.controls,packet,self.world,directory,'d'*64)
            self.assertEqual(result['status'],'confirmed_violation')
            self.assertEqual(result['worlds_attempted'],10)
            self.assertEqual(result['paid_requests'],0)

    def test_conventional_eighth_discovery_stays_within_24_worlds(self):
        experiments = []
        for ordinal in range(8):
            proposal = copy.deepcopy(self.proposal)
            proposal['plan']['actions'][3]['name'] = 'Unit' + str(ordinal)
            experiments.append(proposal)
        last_hash = digest(experiments[-1]['plan'])
        packet = {'case_input_sha256':'d'*64,'preparation':{'kind':'AI_assisted','author':'unit only','provenance_sha256':'e'*64},'experiments':experiments}
        def executor(side, frozen):
            return self.world(side, frozen, 'contract_violated' if frozen['sha256']==last_hash else 'contract_satisfied')
        with tempfile.TemporaryDirectory() as directory:
            result = runner.run_conventional(self.protocol,self.payload,self.controls,packet,executor,directory,'d'*64)
            self.assertEqual(result['status'],'confirmed_violation')
            self.assertEqual(result['worlds_attempted'],24)

    def test_real_client_configuration_has_zero_retries_and_removes_key(self):
        captured = {}
        def client(**kwargs):
            captured.update(kwargs)
            return object()
        with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ', {'MODEL_API_KEY':'unit-private-key'}), patch.dict('sys.modules', {'openai': SimpleNamespace(OpenAI=client)}):
            gateway = runner.MetaGateway.from_environment(directory,self.protocol,'simple_meta')
            import os
            self.assertNotIn('MODEL_API_KEY',os.environ)
            self.assertEqual(captured['max_retries'],0)
            self.assertEqual(captured['base_url'],'https://api.meta.ai/v1')

    def test_subprocess_environment_excludes_host_credentials(self):
        with patch.dict('os.environ', {'MODEL_API_KEY':'private','GITHUB_TOKEN':'private'}):
            environment = child_environment({'POSTGRES_PASS':'disposable'})
        self.assertEqual(set(environment), {'PATH','LANG','POSTGRES_PASS'})
        with self.assertRaises(ValueError):
            child_environment({'MODEL_API_KEY':'must-not-pass'})

    def test_smoke_workflow_has_no_wheel_checkout_or_paid_request(self):
        import yaml
        workflow = yaml.safe_load((ROOT / '.github/workflows/petclinic-runner.yml').read_text())
        job = workflow['jobs']['external-baseline']
        self.assertEqual(job['permissions'],{})
        self.assertFalse(any('checkout' in step.get('uses','') for step in job['steps']))
        code = next(s['run'] for s in job['steps'] if s.get('name')=='Exercise new executor without any model requests')
        self.assertIn((ROOT / 'preflight/petclinic_world.py').read_text(),code)
        self.assertNotIn('MODEL_API_KEY',code)
        self.assertNotIn('completions.create',code)

    def test_actual_v2_freeze(self):
        expected = (ROOT / 'evaluation/petclinic_transfer_protocol_v2.sha256').read_text().strip()
        runner.verify_freeze(ROOT,self.protocol,expected)


if __name__ == '__main__':
    unittest.main()
