import base64
import hashlib
import json
import os
from pathlib import Path
import unittest

from preflight.generic_investigator import implementation_sha256, prepare
from preflight.petclinic_adapter import digest

ROOT=Path(__file__).resolve().parents[1]/'evaluation/generic_paid_integration_v1'


class RegistrationTests(unittest.TestCase):
    def test_completed_report_preserves_abstention_and_limits_claims(self):
        report=json.loads((ROOT/'results.json').read_text())
        self.assertEqual(report['paid_requests'],7)
        self.assertEqual(report['worlds'],20)
        self.assertEqual(report['usage']['total_tokens'],15910)
        self.assertEqual(report['results'][0]['reason'],'model_abstained')
        self.assertEqual(report['results'][0]['observed_status'],'inconclusive')
        self.assertIn('unfamiliar discovery',report['claims_not_supported'])
        self.assertFalse(report['cost_accounting']['invoice_or_credit_balance_verified'])

    def test_audit_rejects_wrong_zip_before_parsing(self):
        from evaluation.generic_paid_integration_v1.audit import audit
        from preflight.petclinic_adapter import AdmissionError
        with self.assertRaises(AdmissionError):audit(b'not the verified artifact')

    @unittest.skipUnless(os.environ.get('WHEEL_GENERIC_PAID_ARCHIVE'),'authenticated paid artifact not supplied')
    def test_replay_complete_paid_integration_without_calls(self):
        from evaluation.generic_paid_integration_v1.audit import audit
        record=json.loads((ROOT/'registration.json').read_text())
        if implementation_sha256()!=record['implementation_sha256']:
            self.skipTest('Historical artifact replay requires its committed implementation')
        actual=audit(Path(os.environ['WHEEL_GENERIC_PAID_ARCHIVE']).read_bytes())
        self.assertEqual(actual,json.loads((ROOT/'results.json').read_text()))

    def test_all_four_known_cases_and_commitments(self):
        record=json.loads((ROOT/'registration.json').read_text())
        self.assertEqual(len(record['cases']),4)
        self.assertEqual(record['max_requests'],8)
        self.assertTrue(record['runtime_outcomes_already_known'])
        self.assertFalse(record['independent_preparer'])
        expectations=json.loads((ROOT/'expectations.json').read_text())
        self.assertEqual(digest(expectations),record['expectations_sha256'])
        for row in record['cases']:
            case=json.loads((ROOT/(row['id']+'.json')).read_text())
            self.assertEqual(digest(case),row['case_sha256'])
            for side in ('baseline','candidate'):
                self.assertEqual(hashlib.sha256(base64.b64decode(case[side+'_base64'])).hexdigest(),case['source'][side+'_sha256'])
            self.assertNotIn('plan',case)
            self.assertNotIn('expected_label',case)

    def test_frozen_inputs_admit_with_complete_schema_without_execution(self):
        record=json.loads((ROOT/'registration.json').read_text())
        if implementation_sha256()!=record['implementation_sha256']:
            self.skipTest('Historical integration registration requires its committed implementation')
        for row in record['cases']:
            c=json.loads((ROOT/(row['id']+'.json')).read_text())
            packet,_=prepare(base64.b64decode(c['baseline_base64']),base64.b64decode(c['candidate_base64']),
                             *[c[k] for k in ('source','manifest','lifecycle','interface','contract','policy')])
            self.assertIn('plan_tool_schema',packet)
            self.assertNotIn('expectations_sha256',json.dumps(packet))
            self.assertNotIn('control_artifact',json.dumps(packet))


if __name__=='__main__':unittest.main()
