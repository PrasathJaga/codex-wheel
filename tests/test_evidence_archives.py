"""Opt-in checks against authenticated historical Actions archives, without inference."""
import hashlib
import json
import os
from pathlib import Path
import zipfile

import pytest
from wheel.evidence_export import export_archive

CASES = [
    ('comparison', '7406e1a3387ddaf1e1df90cb1e1732aa61249843a1d0d8a49da94c7fbb0ca44f', 132),
    ('expanded', '51e285f92fdcc0a4d16d611063130f8f63e9041c81535dd09b066aeade6bfd8a', 108),
    ('interface-v2', '611728f172308ef43344347ad87a797b32169d47179380a0a9c55f3d685a55c8', 12),
]


@pytest.mark.skipif(not os.environ.get('WHEEL_ARCHIVE_DIR'), reason='Authenticated historical archives not supplied')
@pytest.mark.parametrize('name,digest,worlds', CASES)
def test_historical_export_matches_preserved_records(name, digest, worlds):
    archive = Path(os.environ['WHEEL_ARCHIVE_DIR']) / (name + '.zip')
    before = hashlib.sha256(archive.read_bytes()).hexdigest()
    result = export_archive(archive, digest)
    with zipfile.ZipFile(archive) as bundle:
        assert result['worlds'] == json.loads(bundle.read('results.json'))
        for entry in bundle.namelist():
            if entry.endswith('.json') and '/' not in entry:
                assert result['supporting_records'][entry] == json.loads(bundle.read(entry))
        outcomes = json.loads(bundle.read('outcomes.json'))
        assert {p['id']: p['verdict'] for p in result['plans']} == outcomes
        if 'selections.json' in bundle.namelist():
            assert result['selections'] == json.loads(bundle.read('selections.json'))
    assert len(result['worlds']) == worlds
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == before == digest
    if name == 'interface-v2':
        assert result['selections'][0]['status'] == 'inconclusive'
        assert result['selections'][1]['status'] == 'accepted'
        assert result['plans'][0]['verdict']['verdict'] == 'reproduced_regression'
    output = Path(os.environ['WHEEL_ARCHIVE_DIR']) / (name + '-export.json')
    output.write_text(json.dumps(result, indent=2) + '\n')
