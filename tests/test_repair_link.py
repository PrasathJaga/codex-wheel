import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from wheel.repair_link import unpack,match_tested_source

class RepairLinkTests(unittest.TestCase):
    def test_source_and_tests_must_match(self):
        source='healthy reviewed source';sha=hashlib.sha256(source.encode()).hexdigest()
        self.assertEqual(match_tested_source(source,{'repair_sha256':sha},{'returncode':0,'source_sha256':sha}),sha)
        for tests in [{'returncode':1,'source_sha256':sha},{'returncode':0,'source_sha256':'wrong'}]:
            with self.assertRaises(ValueError):match_tested_source(source,{'repair_sha256':sha},tests)
        with self.assertRaises(ValueError):match_tested_source('different',{'repair_sha256':sha},{'returncode':0,'source_sha256':sha})
    def test_archive_authentication_and_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);archive=root/'test.zip';out=root/'out';out.mkdir()
            with zipfile.ZipFile(archive,'w') as z:z.writestr('record.json','{}')
            sha=hashlib.sha256(archive.read_bytes()).hexdigest();unpack(archive,sha,out)
            self.assertEqual(json.loads((out/'record.json').read_text()),{})
            with self.assertRaises(ValueError):unpack(archive,'0'*64,out)
            with zipfile.ZipFile(archive,'w') as z:z.writestr('../escape','bad')
            with self.assertRaises(ValueError):unpack(archive,hashlib.sha256(archive.read_bytes()).hexdigest(),out)

if __name__=='__main__':unittest.main()
