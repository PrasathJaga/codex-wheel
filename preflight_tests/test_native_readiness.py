import copy
import hashlib
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from evaluation.native_readiness_v1.qualify import pinned_requirements,python_readiness,maven_readiness,qualify
from preflight.petclinic_adapter import AdmissionError

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'evaluation/native_readiness_v1'


class NativeReadinessTests(unittest.TestCase):
    def test_source_only_releases_are_not_silently_built_or_upgraded(self):
        evidence=json.loads((DATA/'python-release-evidence.json').read_text())
        raw='\n'.join(r['requirement'] for r in evidence['releases']).encode()+b'\n'
        self.assertEqual(hashlib.sha256(raw).hexdigest(),evidence['requirements_sha256'])
        with patch('subprocess.run',side_effect=AssertionError('No builds')):
            result=python_readiness(raw,evidence)
        self.assertFalse(result['ready_for_native_tests'])
        self.assertEqual(len(result['requirements_without_wheels']),6)
        self.assertIn('Flask==0.10.1',result['requirements_without_wheels'])
        self.assertEqual(result['status'],'blocked_wheel_only_acquisition')

    def test_requirement_options_ranges_and_conflicts_rejected(self):
        for raw in [b'--extra-index-url https://outside.invalid',b'pkg>=1',b'pkg==1\nPkg==2',b'git+https://outside.invalid/repo']:
            with self.assertRaises(AdmissionError):pinned_requirements(raw)

    def test_wheel_presence_does_not_claim_native_or_transitive_compatibility(self):
        raw=b'example==1\n';metadata={'retrieved_on':'unit fixture','requirements_sha256':hashlib.sha256(raw).hexdigest(),
          'releases':[{'requirement':'example==1','metadata_url':'https://pypi.org/pypi/example/1/json',
                       'artifacts':[{'filename':'example-1-py3-none-any.whl','packagetype':'bdist_wheel'}]}]}
        result=python_readiness(raw,metadata)
        self.assertFalse(result['ready_for_native_tests'])
        self.assertEqual(result['status'],'compatibility_and_closure_review_required')
        metadata['releases'][0]['metadata_url']='https://outside.invalid/'
        with self.assertRaises(AdmissionError):python_readiness(raw,metadata)

    def test_maven_metadata_is_not_full_resolution_or_a_build_failure(self):
        raw=b'<project><parent><groupId>x</groupId><artifactId>p</artifactId><version>1</version></parent><dependencies><dependency><groupId>x</groupId><artifactId>test</artifactId><scope>test</scope></dependency></dependencies></project>'
        result=maven_readiness(raw)
        self.assertTrue(result['native_test_dependencies_declared'])
        self.assertFalse(result['transitive_closure_verified'])
        self.assertFalse(result['baseline_executed'])
        self.assertIsNone(result['direct_dependencies'][0]['version'])
        with self.assertRaises(AdmissionError):maven_readiness(b'<!DOCTYPE project><project/>')

    @unittest.skipUnless(os.environ.get('WHEEL_EXTERNAL_INTAKE_DIR'),'authenticated source archives not supplied')
    def test_actual_pinned_source_reports_replay(self):
        folder=Path(os.environ['WHEEL_EXTERNAL_INTAKE_DIR'])
        for cid in ['spring_record_refactor','httpbin_status_fix']:
            descriptor=json.loads((ROOT/'evaluation/external_intake_v1'/ (cid+'-source.json')).read_text())
            profile=json.loads((DATA/(cid+'-profile.json')).read_text())
            metadata=json.loads((DATA/'python-release-evidence.json').read_text()) if profile['language']=='python' else None
            report=qualify(descriptor,(folder/(cid+'-baseline.tar.gz')).read_bytes(),(folder/(cid+'-candidate.tar.gz')).read_bytes(),profile,metadata)
            self.assertEqual(report,json.loads((DATA/(cid+'-readiness.json')).read_text()))
            self.assertFalse(report['desired_native_pass_achieved'])
            self.assertFalse(report['project_or_package_code_executed'])


if __name__=='__main__':unittest.main()
