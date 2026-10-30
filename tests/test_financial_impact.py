import copy
import unittest
from wheel.financial_impact import observed

class ImpactTests(unittest.TestCase):
    def setUp(self):
        self.doc={'plan':{'fixture':{'amount_minor_units':5500}},'worlds':[
            {'world':side,'trial':trial,'status':'completed','effects':[{'effect_id':str(i),'currency':'USD','amount_minor_units':5500} for i in range(count)]}
            for trial in range(3) for side,count in [('base',1),('candidate',2)]]}
    def test_trials_remain_separate(self):
        rows=observed(self.doc)
        self.assertEqual([r['excess_minor_units'] for r in rows],[0,5500]*3)
        self.assertEqual(len(rows),6)
    def test_missing_world_is_unknown_not_zero(self):
        self.doc['worlds'][0]={'world':'base','trial':0,'status':'analysis_error'}
        self.assertIsNone(observed(self.doc)[0]['excess_minor_units'])
    def test_empty_ledger_is_shortfall(self):
        self.doc['worlds'][0]['effects']=[]
        self.assertEqual(observed(self.doc)[0]['shortfall_minor_units'],5500)
    def test_invalid_currency_amount_and_duplicate_identity(self):
        for change in [{'currency':'INR'},{'amount_minor_units':True},{'amount_minor_units':-1}]:
            doc=copy.deepcopy(self.doc);doc['worlds'][0]['effects'][0].update(change)
            with self.assertRaises(ValueError):observed(doc)
        self.doc['worlds'][0]['effects']*=2
        with self.assertRaises(ValueError):observed(self.doc)
