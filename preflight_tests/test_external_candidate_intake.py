import copy
import hashlib
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from evaluation.external_intake_v1.intake import inspect_pair
from preflight.petclinic_adapter import AdmissionError,digest
from preflight_tests.test_project_discovery import archive

ROOT=Path(__file__).resolve().parents[1]/'evaluation/external_intake_v1'


def fixture():
    a=archive({'pyproject.toml':b'[project]\nname="test"','app.py':b'raise RuntimeError("never execute")'})
    b=archive({'pyproject.toml':b'[project]\nname="test"','app.py':b'raise RuntimeError("never execute changed")'})
    d={'id':'unit_source','repo':'example/project','reference':'https://github.com/example/project/commit/'+'a'*40,
       'kind':'historical_change','paths':['app.py'],'blockers':['unit fixture only'],'archives':{}}
    for side,raw,sha in [('baseline',a,'a'*40),('candidate',b,'b'*40)]:
        d['archives'][side]={'revision':sha,'url':'https://codeload.github.com/example/project/tar.gz/'+sha,
                            'root':'repo','size_bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    return d,a,b


class IntakeTests(unittest.TestCase):
    def test_source_verification_is_not_execution_or_review(self):
        d,a,b=fixture()
        with patch('subprocess.run',side_effect=AssertionError('No execution')):
            report=inspect_pair(d,a,b)
        self.assertTrue(report['source_integrity_verified'])
        self.assertFalse(report['comparison_eligible'])
        self.assertFalse(report['independent_case_preparation_verified'])
        self.assertFalse(report['project_code_executed'])
        self.assertEqual(report['model_requests'],0)

    def test_wrong_archive_and_origin_rejected(self):
        d,a,b=fixture()
        with self.assertRaises(AdmissionError):inspect_pair(d,a,b+b'changed')
        d['archives']['candidate']['url']='https://outside.invalid/source'
        with self.assertRaises(AdmissionError):inspect_pair(d,a,b)

    def test_metadata_cannot_hide_actual_changed_paths(self):
        d,a,b=fixture();d['paths']=[]
        with self.assertRaisesRegex(AdmissionError,'complete diff'):inspect_pair(d,a,b)

    def test_catalog_preserves_rejections_and_has_no_registered_cases(self):
        catalog=json.loads((ROOT/'catalog.json').read_text())
        self.assertEqual(catalog['runtime_cases_registered'],0)
        self.assertEqual(len(catalog['rejected_during_screening']),3)
        for cid in ['spring_record_refactor','httpbin_status_fix']:
            d=json.loads((ROOT/(cid+'-source.json')).read_text());r=json.loads((ROOT/(cid+'-intake.json')).read_text())
            self.assertEqual(r['descriptor_sha256'],digest(d))
            self.assertFalse(r['comparison_eligible']);self.assertTrue(r['blockers'])
        python_report=json.loads((ROOT/'httpbin_status_fix-intake.json').read_text())
        self.assertIn('test_httpbin.py',python_report['test_paths_changed'])

    @unittest.skipUnless(os.environ.get('WHEEL_EXTERNAL_INTAKE_DIR'),'authenticated public archives not supplied')
    def test_replay_actual_public_source_pairs(self):
        folder=Path(os.environ['WHEEL_EXTERNAL_INTAKE_DIR'])
        for cid in ['spring_record_refactor','httpbin_status_fix']:
            d=json.loads((ROOT/(cid+'-source.json')).read_text())
            r=inspect_pair(d,(folder/(cid+'-baseline.tar.gz')).read_bytes(),(folder/(cid+'-candidate.tar.gz')).read_bytes())
            self.assertEqual(r,json.loads((ROOT/(cid+'-intake.json')).read_text()))


if __name__=='__main__':unittest.main()
