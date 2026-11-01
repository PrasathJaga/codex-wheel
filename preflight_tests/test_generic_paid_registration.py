import base64
import hashlib
import json
from pathlib import Path
import unittest

from preflight.generic_investigator import implementation_sha256, prepare
from preflight.petclinic_adapter import digest

ROOT=Path(__file__).resolve().parents[1]/'evaluation/generic_paid_integration_v1'


class RegistrationTests(unittest.TestCase):
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
