import hashlib
import io
import json
import os
from pathlib import Path
import unittest
import zipfile

from preflight.petclinic_adapter import AdmissionError
from preflight.petclinic_pilot_audit import audit_archive

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = os.environ.get('WHEEL_PILOT_RESULT_ARCHIVE')


class PilotAuditTests(unittest.TestCase):
    def test_rejects_wrong_artifact_digest_before_parsing(self):
        with self.assertRaisesRegex(AdmissionError, 'digest mismatch'):
            audit_archive(b'not the evidence archive', ROOT)

    def test_rejects_duplicate_or_traversal_archive_members(self):
        for names in (['duplicate', 'duplicate'], ['../escape']):
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w') as z:
                for name in names:
                    z.writestr(name, '{}')
            raw = stream.getvalue()
            with self.assertRaisesRegex(AdmissionError, 'Unsafe archive'):
                audit_archive(raw, ROOT, hashlib.sha256(raw).hexdigest())

    def test_published_result_blocks_evaluation_claims(self):
        result = json.loads((ROOT / 'evaluation/petclinic_pilot_v2_results.json').read_text())
        self.assertFalse(result['evaluation_ready_for_repair_or_superiority_claim'])
        self.assertEqual(result['expectation_mismatches'], ['pc-001'])
        self.assertEqual(result['paid_requests'], 4)
        self.assertEqual(result['worlds_attempted'], 28)
        self.assertEqual(len(result['methods']), 6)
        self.assertFalse(result['cost_accounting']['invoice_or_credit_balance_verified'])

    @unittest.skipUnless(ARCHIVE, 'authenticated pilot artifact not supplied')
    def test_replays_actual_artifact_and_exact_published_report(self):
        raw = Path(ARCHIVE).read_bytes()
        result = audit_archive(raw, ROOT)
        published = json.loads((ROOT / 'evaluation/petclinic_pilot_v2_results.json').read_text())
        self.assertEqual(result, published)
        admitted = [m['selection_review'] for m in result['methods'] if m['selection_review']]
        self.assertEqual(sum(s['admission'] == 'rejected' for s in admitted), 3)
        self.assertEqual(sum(s['recorded_status'] == 'abstain' for s in admitted), 1)

    @unittest.skipUnless(ARCHIVE, 'authenticated pilot artifact not supplied')
    def test_world_tampering_rejected_even_with_new_archive_digest(self):
        original = zipfile.ZipFile(ARCHIVE)
        stream = io.BytesIO()
        target = 'pc-001/source_aware_conventional/runtime/world-4/result.json'
        with zipfile.ZipFile(stream, 'w') as changed:
            for name in original.namelist():
                data = original.read(name)
                if name == target:
                    value = json.loads(data)
                    value['status'] = 'contract_satisfied'
                    data = json.dumps(value).encode()
                changed.writestr(name, data)
        raw = stream.getvalue()
        with self.assertRaisesRegex(AdmissionError, 'World evidence changed'):
            audit_archive(raw, ROOT, hashlib.sha256(raw).hexdigest())


if __name__ == '__main__':
    unittest.main()
