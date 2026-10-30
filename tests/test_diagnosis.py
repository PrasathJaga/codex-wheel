import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock
import unittest
import tempfile
from pathlib import Path
from wheel import diagnosis as d


class DiagnosisTests(unittest.TestCase):
    def setUp(self):
        self.packet = {'verdict': {'verdict': 'reproduced_regression'}, 'plan': {'id': 'P'},
                       'worlds': [{'effects': [1, 2], 'model_reply': None}],
                       'source_snapshots': {'java': 'source'}, 'limitations': []}
        self.result = {'status': 'explained', 'explanation': 'Observed duplicate effects; retry is the proposed explanation.',
                       'references': [{'pointer': '/' + k, 'value': v} for k, v in self.packet.items() if k != 'limitations']}

    def test_valid_references_do_not_mutate_evidence(self):
        before = copy.deepcopy(self.packet)
        self.assertEqual(d.validate(self.packet, self.result), self.result)
        self.assertEqual(before, self.packet)

    def test_fabricated_or_missing_references_rejected(self):
        for pointer in ['/absent', '/worlds/5', '/worlds/00', '/bad~escape']:
            result = copy.deepcopy(self.result)
            result['references'][0]['pointer'] = pointer
            with self.assertRaises((ValueError, KeyError, IndexError)):
                d.validate(self.packet, result)
        result = copy.deepcopy(self.result)
        result['references'][0]['value'] = 'invented'
        with self.assertRaises(ValueError): d.validate(self.packet, result)
        result['references'] = []
        with self.assertRaises(ValueError): d.validate(self.packet, result)

    def test_unknown_source_requires_abstention(self):
        self.packet['source_snapshots'] = None
        with self.assertRaises(ValueError): d.validate(self.packet, self.result)
        self.assertEqual(d.validate(self.packet, {'status': 'abstained', 'explanation': 'Missing source.', 'references': []})['status'], 'abstained')

    def test_one_request_preserved_and_no_overwrite(self):
        client = Mock()
        response = SimpleNamespace(id='mock-response', model=d.MODEL, usage=None,
            choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(content=json.dumps(self.result)))],
            model_dump=lambda **kw: {'test_only': True, 'content': self.result})
        client.chat.completions.create.return_value = response
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'attempt.json'
            result = d.request_diagnosis(client, self.packet, path)
            self.assertEqual(result['status'], 'explained')
            self.assertEqual(result['semantic_review'], 'required')
            self.assertEqual(result['protected_verdict'], self.packet['verdict'])
            self.assertEqual(json.loads(path.read_text())['response_id'], 'mock-response')
            with self.assertRaises(FileExistsError): d.request_diagnosis(client, self.packet, path)
        self.assertEqual(client.chat.completions.create.call_count, 1)

    def test_request_failure_preserved_without_sensitive_error(self):
        client = Mock()
        client.chat.completions.create.side_effect = RuntimeError('SECRET_BODY')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'attempt.json'
            self.assertEqual(d.request_diagnosis(client, self.packet, path)['status'], 'request_error')
            self.assertNotIn('SECRET_BODY', path.read_text())
        self.assertEqual(client.chat.completions.create.call_count, 1)

    def test_invalid_response_retained_without_retry(self):
        client = Mock()
        client.chat.completions.create.return_value = SimpleNamespace(id='mock', model=d.MODEL, usage=None,
            choices=[SimpleNamespace(finish_reason='length')], model_dump=lambda **kw: {'raw': 'incomplete'})
        with tempfile.TemporaryDirectory() as tmp:
            result = d.request_diagnosis(client, self.packet, Path(tmp) / 'attempt.json')
        self.assertEqual(result['status'], 'rejected')
        self.assertEqual(result['response'], {'raw': 'incomplete'})
        self.assertEqual(client.chat.completions.create.call_count, 1)


if __name__ == '__main__': unittest.main()
