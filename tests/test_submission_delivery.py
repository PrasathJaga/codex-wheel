import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class SubmissionDeliveryTests(unittest.TestCase):
    def test_published_evidence_keeps_actual_outcomes_and_scope(self):
        data=json.loads((ROOT/'delivery/evidence.json').read_text())
        self.assertEqual(data['refund']['authorized_minor_units'],2000)
        self.assertEqual(data['refund']['candidate_committed_minor_units'],4000)
        self.assertEqual(data['refund']['observed_excess_minor_units'],2000)
        self.assertEqual(data['generic_meta']['results'][0]['status'],'inconclusive')
        self.assertEqual(data['external_onboarding'],'not_completed')
        self.assertEqual(data['assembly_model_requests'],0)
        page=(ROOT/'delivery/index.html').read_text()
        for phrase in ('Recorded API receipt','USD 40.00','Python preserving remains inconclusive','Healthy repair answer supplied'):
            self.assertIn(phrase,page)

    @unittest.skipUnless(os.environ.get('WHEEL_SUBMISSION_EVIDENCE_DIR'),'authenticated delivery archives not supplied')
    def test_archive_rebuild_and_tampered_input_rejection(self):
        from delivery.build_submission import build
        folder=Path(os.environ['WHEEL_SUBMISSION_EVIDENCE_DIR'])
        files=[folder/n for n in ('fresh-pr-cycle-v2.zip','inventory-repair-v1.zip','fresh-pr-cycle-failure.zip','generic-meta-integration-v1-verified.zip')]
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'valid';build(*files,output)
            self.assertEqual((output/'index.html').read_text(),(ROOT/'delivery/index.html').read_text())
            invalid=Path(tmp)/'invalid.zip';invalid.write_bytes(b'changed archive')
            with self.assertRaises(ValueError):build(invalid,*files[1:],Path(tmp)/'invalid')
            self.assertFalse((Path(tmp)/'invalid/index.html').exists())


if __name__=='__main__':unittest.main()
