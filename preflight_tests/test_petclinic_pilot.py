import json
import os
from pathlib import Path
import unittest

import yaml
from preflight.petclinic_adapter import digest, freeze_plan
from preflight.petclinic_evaluation import build_case, model_input
from preflight.petclinic_meta_runner import validate_selection, verify_freeze
from preflight.petclinic_pilot import cost_accounting

ROOT = Path(__file__).resolve().parents[1]


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.protocol = json.loads((ROOT / 'evaluation/petclinic_transfer_protocol_v2.json').read_text())
        self.registry = json.loads((ROOT / 'evaluation/petclinic_transfer_registry_v2.json').read_text())

    def test_frozen_runner_and_two_predeclared_internal_cases(self):
        verify_freeze(ROOT,self.protocol,(ROOT / 'evaluation/petclinic_transfer_protocol_v2.sha256').read_text().strip())
        self.assertEqual(self.registry['attempts'],[])
        self.assertEqual([r['id'] for r in self.registry['cases']],['pc-001','pc-002'])
        labels = []
        for record in self.registry['cases']:
            case_id = record['id']
            case = json.loads((ROOT / f'evaluation/petclinic_cases_v2/{case_id}.json').read_text())
            expected = json.loads((ROOT / f'evaluation/petclinic_cases_v2/{case_id}-expectation.json').read_text())
            self.assertEqual(record['case_input_sha256'],digest(case))
            self.assertEqual(case['expectation_commitment_sha256'],digest(expected))
            self.assertEqual(record['independence_status'],'not_independent')
            self.assertEqual(record['source_admission']['changed_paths'],[case['replacements'][0]['path']])
            labels.append(expected['expected_label'])
        self.assertEqual(sorted(labels),['preserving','violating'])

    def test_conventional_packets_bound_and_finite(self):
        for record in self.registry['cases']:
            packet = json.loads((ROOT / f"evaluation/petclinic_cases_v2/{record['id']}-conventional.json").read_text())
            self.assertEqual(packet['case_input_sha256'],record['case_input_sha256'])
            self.assertEqual(packet['preparation']['kind'],'AI_assisted')
            self.assertEqual(len(packet['experiments']),4)
            for experiment in packet['experiments']:
                freeze_plan(experiment['plan'])

    @unittest.skipUnless(os.environ.get('WHEEL_PILOT_ARCHIVE'),'public archive not supplied for registration-only replay')
    def test_rebuild_exact_registrations_without_model_or_java(self):
        archive = Path(os.environ['WHEEL_PILOT_ARCHIVE']).read_bytes()
        for record in self.registry['cases']:
            case_id = record['id']
            case = json.loads((ROOT / f'evaluation/petclinic_cases_v2/{case_id}.json').read_text())
            bundle = build_case(case,archive,self.protocol)
            self.assertEqual(bundle['record'],record)
            payload = model_input(bundle,self.protocol)
            text = json.dumps(payload)
            self.assertNotIn('expectation_commitment_sha256',text)
            self.assertNotIn('expected_label',text)
            self.assertNotIn('reference_repair_sha256',text)
            packet = json.loads((ROOT / f'evaluation/petclinic_cases_v2/{case_id}-conventional.json').read_text())
            for experiment in packet['experiments']:
                validate_selection(experiment,payload)

    def test_no_paid_pull_request_or_automatic_rerun(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/petclinic-pilot.yml').read_text())
        job = workflow['jobs']['trusted-pilot-controller']
        self.assertIn("github.event_name == 'push'",job['if'])
        self.assertIn('github.run_attempt == 1',job['if'])
        self.assertIn('evaluation/petclinic-pilot-live-once',job['if'])
        self.assertNotIn('secrets.',json.dumps(workflow['jobs']['pilot-registration-tests']))
        self.assertTrue(any('prior live launch' in s.get('run','') for s in job['steps']))

    def test_cost_estimates_are_usage_based_and_unknown_stays_unknown(self):
        known = cost_accounting([{'usage':{'prompt_tokens':1000,'completion_tokens':100,'prompt_tokens_details':{'cached_tokens':200}}}])
        self.assertAlmostEqual(known['estimated_standard_token_charge_usd'],0.001455)
        unknown = cost_accounting([{'usage':None}])
        self.assertIsNone(unknown['estimated_standard_token_charge_usd'])
        self.assertFalse(unknown['complete_reported_usage'])
        self.assertFalse(known['invoice_or_credit_balance_verified'])


if __name__ == '__main__':
    unittest.main()
