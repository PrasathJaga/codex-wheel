import copy
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from preflight import petclinic_evaluation as evaluation
from preflight.petclinic_adapter import AdmissionError, EDIT_PATHS, digest

ROOT = Path(__file__).resolve().parents[1]


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.protocol = json.loads((ROOT / 'evaluation/petclinic_transfer_protocol_v1.json').read_text())
        self.sha = (ROOT / 'evaluation/petclinic_transfer_protocol_v1.sha256').read_text().strip()
        output = io.BytesIO()
        self.files = {p: b'class Original {}\n' for p in EDIT_PATHS}
        self.files['pom.xml'] = b'unchanged build'
        root = 'spring-petclinic-rest-' + self.protocol['upstream_revision']
        self.archive = evaluation.case_archive(self.files, root)
        self.unit_protocol = {**self.protocol, 'baseline_archive_sha256': hashlib.sha256(self.archive).hexdigest()}
        path = sorted(EDIT_PATHS)[0]
        self.case = {'id': 'pc-001', 'infrastructure_revision': self.protocol['infrastructure_revision'],
                     'preparation': {'kind': 'internal_transfer', 'author': 'unit-test-only', 'provenance_sha256': 'e'*64},
                     'expectation_commitment_sha256': 'f'*64,
                     'replacements': [{'path': path, 'before_sha256': hashlib.sha256(self.files[path]).hexdigest(),
                                       'content': 'class Changed {}\n'}]}

    def test_actual_freeze_and_protocol_integrity(self):
        evaluation.verify_protocol(ROOT, self.protocol, self.sha)
        changed = copy.deepcopy(self.protocol)
        changed['methods']['wheel_meta']['selection_requests'] = 2
        with self.assertRaises(AdmissionError):
            evaluation.verify_protocol(ROOT, changed, self.sha)

    def test_case_intake_uses_whole_source_and_preserves_build_files(self):
        bundle = evaluation.build_case(self.case, self.archive, self.unit_protocol)
        self.assertEqual(bundle['candidate']['pom.xml'], b'unchanged build')
        self.assertEqual(set(bundle['candidate']), set(self.files))
        self.assertEqual(bundle['record']['status'], 'registered_not_executed')
        self.assertEqual(bundle['record']['independence_status'], 'not_independent')

    def test_labels_provenance_and_reference_checks_not_in_model_payload(self):
        case = copy.deepcopy(self.case)
        case['preparation']['author'] = 'PRIVATE EXPECTED LABEL AND REFERENCE'
        bundle = evaluation.build_case(case, self.archive, self.unit_protocol)
        payload = evaluation.model_input(bundle, self.unit_protocol)
        text = json.dumps(payload)
        self.assertNotIn('PRIVATE EXPECTED LABEL', text)
        self.assertNotIn(case['expectation_commitment_sha256'], text)
        self.assertEqual(set(payload), {'contract','action_interface','baseline_sources','candidate_sources','diff'})
        self.assertEqual(set(payload['baseline_sources']), set(EDIT_PATHS))

    def test_reject_unsupported_stale_noop_and_unknown_case_input(self):
        for mutate in (
            lambda c: c.update(expected_label='violating'),
            lambda c: c['replacements'][0].update(path='pom.xml'),
            lambda c: c['replacements'][0].update(before_sha256='0'*64),
            lambda c: c['replacements'][0].update(content='class Original {}\n'),
            lambda c: c.update(infrastructure_revision='0'*40),
        ):
            case = copy.deepcopy(self.case)
            mutate(case)
            with self.subTest(case=case), self.assertRaises(AdmissionError):
                evaluation.build_case(case, self.archive, self.unit_protocol)

    def test_independent_claim_is_not_automatically_verified(self):
        case = copy.deepcopy(self.case)
        case['preparation']['kind'] = 'independent_developer'
        bundle = evaluation.build_case(case, self.archive, self.unit_protocol)
        self.assertEqual(bundle['record']['independence_status'], 'declared_unverified')

    def test_registry_prevents_replacement_and_resampling(self):
        bundle = evaluation.build_case(self.case, self.archive, self.unit_protocol)
        registry = {'protocol_sha256': digest(self.unit_protocol), 'cases': [], 'attempts': []}
        registry = evaluation.register_record(registry, bundle['record'], self.unit_protocol)
        with self.assertRaises(AdmissionError):
            evaluation.register_record(registry, bundle['record'], self.unit_protocol)
        registry = evaluation.start_attempt(registry, 'pc-001', 'wheel_meta', self.unit_protocol)
        with self.assertRaises(AdmissionError):
            evaluation.start_attempt(registry, 'pc-001', 'wheel_meta', self.unit_protocol)
        with self.assertRaises(AdmissionError):
            evaluation.start_attempt(registry, 'pc-002', 'wheel_meta', self.unit_protocol)

    def test_duplicate_json_keys_and_silent_context_truncation_rejected(self):
        with self.assertRaises(AdmissionError):
            evaluation.strict_json('{"id":1,"id":2}')
        bundle = evaluation.build_case(self.case, self.archive, self.unit_protocol)
        with self.assertRaises(AdmissionError):
            evaluation.model_input(bundle, {**self.unit_protocol, 'max_model_input_bytes': 1})

    def test_disk_registration_preserves_existing_case_and_registry(self):
        bundle = evaluation.build_case(self.case, self.archive, self.unit_protocol)
        payload = evaluation.model_input(bundle, self.unit_protocol)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = root / 'registry.json'
            registry.write_text(json.dumps({'protocol_sha256': digest(self.unit_protocol), 'cases': [], 'attempts': []}))
            evaluation.save_registration(root / 'case-1', registry, bundle, payload, self.unit_protocol)
            prior = registry.read_bytes()
            with self.assertRaises(AdmissionError):
                evaluation.save_registration(root / 'case-2', registry, bundle, payload, self.unit_protocol)
            self.assertEqual(prior, registry.read_bytes())
            self.assertFalse((root / 'case-2').exists())
            self.assertEqual(len(json.loads(prior)['cases']), 1)


if __name__ == '__main__':
    unittest.main()
