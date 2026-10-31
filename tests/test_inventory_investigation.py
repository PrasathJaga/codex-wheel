import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location('inventory_investigation',Path(__file__).resolve().parents[1]/'wheel/inventory_investigation.py')
adapter = importlib.util.module_from_spec(spec); spec.loader.exec_module(adapter)


def sources():
    return {adapter.SOURCE:{'base':'old guard\n    return value;\n','candidate':'    return value;\n'},
            adapter.PEER:{'base':'    confirmation()\n','candidate':'    confirmation()\n'}}


def proposal():
    return {'status':'proposed','reason':'Inspect the changed lifecycle guard and consumer confirmation.',
            'actions':[{'op':'RESERVE','buyer':'A'},{'op':'CHECKOUT','buyer':'A'}],
            'citations':[{'path':adapter.SOURCE,'version':'candidate','start':1,'end':1,'quote':'    return value;'},
                         {'path':adapter.PEER,'version':'base','start':1,'end':1,'quote':'    confirmation()'}]}


class InventoryInvestigationTests(unittest.TestCase):
    def test_valid_source_cited_sequence(self):
        item = proposal(); self.assertEqual(adapter.validate(item,sources()),item)

    def test_abstention_retained(self):
        item = {'status':'abstained','reason':'Insufficient evidence'}
        self.assertEqual(adapter.validate(item,sources()),item)

    def test_action_cap_and_allowlist(self):
        for action in [{'op':'SHELL','buyer':'A'},{'op':'RESERVE','buyer':'C'},
                       {'op':'RESERVE','buyer':'A','url':'https://example.com'}]:
            item=proposal(); item['actions'][0]=action
            with self.subTest(action=action), self.assertRaises(ValueError): adapter.validate(item,sources())
        item=proposal(); item['actions']*=5
        with self.assertRaises(ValueError): adapter.validate(item,sources())

    def test_reservation_required_before_use(self):
        item=proposal();item['actions'].reverse()
        with self.assertRaises(ValueError): adapter.validate(item,sources())

    def test_exact_quotes_and_peer_base_required(self):
        for replacement in [{'quote':'return value;'}, {'start':0}, {'end':9}, {'start':True}, {'version':'unknown'}]:
            item=proposal();item['citations'][0].update(replacement)
            with self.subTest(replacement=replacement),self.assertRaises(ValueError): adapter.validate(item,sources())
        item=proposal();item['citations'][1]['version']='candidate'
        with self.assertRaises(ValueError): adapter.validate(item,sources())

    def test_extra_fields_and_invented_source_rejected(self):
        item=proposal();item['verdict']='passed'
        with self.assertRaises(ValueError): adapter.validate(item,sources())
        item=proposal();item['citations'][0]['path']='invented.java'
        with self.assertRaises(ValueError): adapter.validate(item,sources())

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(ValueError): adapter.parse('{"status":"proposed","status":"abstained"}')

    def test_verdicts_distinguish_errors_and_violations(self):
        def rows(a,b): return [{'status':x} for _ in range(3) for x in (a,b)]
        self.assertEqual(adapter.verdict(rows('pass','contract_violation')),'reproduced_regression')
        self.assertEqual(adapter.verdict(rows('pass','pass')),'not_reproduced')
        self.assertEqual(adapter.verdict(rows('pass','execution_error')),'execution_error')
        self.assertEqual(adapter.verdict(rows('contract_violation','pass')),'invalid_baseline')
        self.assertEqual(adapter.verdict([]),'inconclusive')

    def test_one_response_and_request_receipt(self):
        client=Mock(); response=Mock()
        response.id='provider-id';response.model=adapter.MODEL
        response.usage.model_dump.return_value={'total_tokens':123}
        response.model_dump.return_value={'id':'provider-id'}
        response.choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content=json.dumps(proposal())))]
        client.chat.completions.create.return_value=response
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)
            self.assertEqual(adapter.select(client,sources(),out,{'max_completion_tokens':6000}),proposal())
            receipt=json.loads((out/'model-request.json').read_text())
            self.assertEqual(receipt['admission'],'proposed');self.assertEqual(receipt['usage']['total_tokens'],123)
            with self.assertRaises(FileExistsError): adapter.select(client,sources(),out,{'max_completion_tokens':6000})
            self.assertEqual(client.chat.completions.create.call_count,1)

    def test_provider_failure_preserved_without_error_body_or_retry(self):
        client=Mock();client.chat.completions.create.side_effect=RuntimeError('SECRET_BODY')
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)
            with self.assertRaises(RuntimeError): adapter.select(client,sources(),out,{'max_completion_tokens':6000})
            self.assertNotIn('SECRET_BODY',(out/'model-request.json').read_text())
            self.assertEqual(client.chat.completions.create.call_count,1)


if __name__ == '__main__': unittest.main()
