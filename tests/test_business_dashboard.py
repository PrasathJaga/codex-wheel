import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from wheel.business_dashboard import render, diagnosis_record
from wheel.diagnosis import canonical


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.doc={'plan':{'fixture':{'amount_minor_units':5500},'rule':{'action':'REPLACE_DOWNSTREAM_STATUS_502'}},
                  'verdict':{'verdict':'reproduced_regression'},'provenance':{}, 'source_snapshots':{},
                  'worlds':[{'status':'completed','world':side,'trial':0,'effects':[{'effect_id':str(i),'amount_minor_units':5500,'currency':'USD'} for i in range(count)], 'events':[], 'model_reply':None} for side,count in [('base',1),('candidate',2)]]}
        self.record={'status':'explained','packet':self.doc,'protected_verdict':self.doc['verdict'],
                     'evidence_sha256':hashlib.sha256(canonical(self.doc).encode()).hexdigest(),
                     'diagnosis':{'status':'explained','explanation':'<script>bad()</script>', 'references':[{'pointer':'/'+k,'value':self.doc[k]} for k in ['plan','verdict','worlds','source_snapshots']]}}

    def test_real_values_and_no_fabricated_conversation(self):
        page=render(self.doc,self.record,[{'status':'inconclusive'}])
        self.assertIn('USD 55.00',page);self.assertIn('USD 110.00',page)
        self.assertIn('no agent conversation recorded',page)
        self.assertIn('inconclusive',page)
        self.assertNotIn('<script>bad()',page)
        self.assertEqual(page.count('<script>'),1)
        self.assertIn('&lt;script&gt;',page)
        self.assertIn('href="#ref-0"',page)

    def test_diagnosis_must_bind_to_exact_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'diagnosis.zip'
            with zipfile.ZipFile(path,'w') as z:z.writestr('attempt.json',json.dumps(self.record))
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            diagnosis_record(path,digest,self.doc)
            altered=copy.deepcopy(self.doc);altered['worlds'][0]['effects']=[]
            with self.assertRaises(ValueError):diagnosis_record(path,digest,altered)
            with self.assertRaises(ValueError):diagnosis_record(path,'0'*64,self.doc)


if __name__=='__main__': unittest.main()
