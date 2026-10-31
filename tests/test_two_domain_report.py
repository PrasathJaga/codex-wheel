import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('two_domain_report',Path(__file__).resolve().parents[1]/'wheel/two_domain_report.py')
report=importlib.util.module_from_spec(spec);spec.loader.exec_module(report)


class ReportTests(unittest.TestCase):
    def test_pair_inventory_requires_unique_trials(self):
        rows=[{'trial':t,'side':s} for t in range(3) for s in ('base','candidate')]
        report.pair_identity(rows,'side')
        rows[-1]=rows[0]
        with self.assertRaises(ValueError):report.pair_identity(rows,'side')

    def test_provider_usage_deduplicates_by_rejecting_duplicate_receipts(self):
        rows=[{'response_id':'one','model':'muse-spark-1.3','usage':{'total_tokens':10}}]
        self.assertEqual(report.usage(rows)['tokens'],10)
        with self.assertRaises(ValueError):report.usage(rows*2)
        with self.assertRaises(ValueError):report.usage([{**rows[0],'model':'other'}])

    def test_recorded_text_escaped_and_after_stage_hidden(self):
        stage={'cards':[('Baseline','0','No order')],'verdict':'pass','trials':[('0','1')],'evidence':{'text':'</pre><script>alert(1)</script>'}}
        value=report.domain_card('inventory','Title','Description',stage,stage,'<script>bad()</script>',
                                 ['Reserve'],[{'quote':'<img onerror=bad>'}],'Known fixture')
        self.assertNotIn('<script>',value)
        self.assertIn('&lt;script&gt;',value)
        self.assertIn('data-panel="inventory-repaired" hidden',value)

    def test_currency_is_integer_minor_units(self):
        self.assertEqual(report.money(2000),'USD 20.00')
        self.assertEqual(report.money(200001),'USD 2,000.01')


if __name__=='__main__':unittest.main()
