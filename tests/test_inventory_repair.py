import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('inventory_repair',ROOT/'wheel/inventory_repair.py')
repair=importlib.util.module_from_spec(spec);spec.loader.exec_module(repair)
spec=importlib.util.spec_from_file_location('inventory_investigation',ROOT/'wheel/inventory_investigation.py')
inv=importlib.util.module_from_spec(spec);spec.loader.exec_module(inv)


class InventoryRepairTests(unittest.TestCase):
    def test_exact_restoration_admitted(self):
        item={'old_text':'return x;','new_text':'guard();\nreturn x;','reason':'Restore the supplied guard'}
        self.assertEqual(repair.apply_proposal(item,'return x;','guard();\nreturn x;'),'guard();\nreturn x;')

    def test_extra_edits_paths_or_ambiguous_spans_rejected(self):
        item={'old_text':'x','new_text':'guard x','reason':'restore'}
        for candidate,healthy in [('xx','guard xx'),('x','guard x extra'),('none','guard x')]:
            with self.subTest(candidate=candidate),self.assertRaises(ValueError):repair.apply_proposal(item,candidate,healthy)
        with self.assertRaises(ValueError):repair.apply_proposal({**item,'path':'other'},'x','guard x')

    def test_empty_oversized_or_noop_proposal_rejected(self):
        for item in [{'old_text':'','new_text':'guard x','reason':'r'},
                     {'old_text':'x','new_text':'x','reason':'r'},
                     {'old_text':'x','new_text':'guard x','reason':'r'*5001}]:
            with self.subTest(item=str(item)[:80]),self.assertRaises(ValueError):repair.apply_proposal(item,'x','guard x')

    def test_one_request_and_preserved_receipt(self):
        client=Mock();response=Mock();response.id='repair-provider-id';response.model=repair.MODEL
        response.usage.model_dump.return_value={'total_tokens':99}
        response.model_dump.return_value={'id':response.id}
        item={'old_text':'x','new_text':'guard x','reason':'restore'}
        response.choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content=json.dumps(item)))]
        client.chat.completions.create.return_value=response
        with tempfile.TemporaryDirectory() as directory,patch.dict(sys.modules,{'wheel.inventory_investigation':inv}):
            out=Path(directory)
            self.assertEqual(repair.select(client,{},out,{'max_completion_tokens':6000}),item)
            self.assertEqual(json.loads((out/'repair-request.json').read_text())['usage']['total_tokens'],99)
            with self.assertRaises(FileExistsError):repair.select(client,{},out,{'max_completion_tokens':6000})
            self.assertEqual(client.chat.completions.create.call_count,1)

    def test_provider_errors_do_not_leak_or_retry(self):
        client=Mock();client.chat.completions.create.side_effect=RuntimeError('SECRET_BODY')
        with tempfile.TemporaryDirectory() as directory,patch.dict(sys.modules,{'wheel.inventory_investigation':inv}):
            out=Path(directory)
            with self.assertRaises(RuntimeError):repair.select(client,{},out,{'max_completion_tokens':6000})
            self.assertNotIn('SECRET_BODY',(out/'repair-request.json').read_text())
            self.assertEqual(client.chat.completions.create.call_count,1)

    def test_truncated_response_is_not_repaired_manually(self):
        client=Mock();response=Mock();response.id='truncated';response.model=repair.MODEL
        response.usage=None;response.model_dump.return_value={'id':'truncated'}
        response.choices=[SimpleNamespace(finish_reason='length',message=SimpleNamespace(content='{"old_text":'))]
        client.chat.completions.create.return_value=response
        with tempfile.TemporaryDirectory() as directory,patch.dict(sys.modules,{'wheel.inventory_investigation':inv}):
            out=Path(directory)
            with self.assertRaises(ValueError):repair.select(client,{},out,{'max_completion_tokens':6000})
            self.assertEqual(json.loads((out/'repair-request.json').read_text())['status'],'request_error')
            self.assertEqual(client.chat.completions.create.call_count,1)


if __name__=='__main__':unittest.main()
