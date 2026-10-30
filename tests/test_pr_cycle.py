import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import tempfile
import unittest
from wheel.pr_cycle import CycleLedger

class CycleTests(unittest.TestCase):
    def test_failed_requests_count_and_roles_are_bounded(self):
        client=Mock();client.chat.completions.create.side_effect=RuntimeError('SECRET_BODY')
        request={'model':'muse-spark-1.3','max_completion_tokens':2048,'reasoning_effort':'low','messages':[]}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'requests.json';ledger=CycleLedger(client,path)
            for role,cap in [('investigation',6),('diagnosis',1),('repair',1)]:
                for _ in range(cap):
                    with self.assertRaises(RuntimeError):ledger.scoped(role).chat.completions.create(**request)
                with self.assertRaises(RuntimeError):ledger.scoped(role).chat.completions.create(**request)
            self.assertEqual(len(ledger.attempts),8)
            self.assertNotIn('SECRET_BODY',path.read_text())
            self.assertEqual(client.chat.completions.create.call_count,8)
    def test_bad_policy_never_calls_provider(self):
        client=Mock()
        with tempfile.TemporaryDirectory() as tmp:
            ledger=CycleLedger(client,Path(tmp)/'attempts.json')
            with self.assertRaises(ValueError):ledger.scoped('repair').chat.completions.create(model='other')
            client.chat.completions.create.assert_not_called()

if __name__=='__main__':unittest.main()
