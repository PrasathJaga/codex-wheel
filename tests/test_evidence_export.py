import hashlib
import json
import zipfile

import pytest
from wheel.evidence_export import export_archive
from wheel.plan_guard import IntegrityError
from test_report_visualizer import evidence


def bundle(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    _, rows = evidence(source)
    rows[0]['unrecognized_future_field'] = None
    (source / 'results.json').write_text(json.dumps(rows))
    selections = [{'status': 'abstained'}, {'status': 'error', 'error_type': 'Example'}]
    (source / 'selections.json').write_text(json.dumps(selections))
    (source / 'investigator-traces.json').write_text(json.dumps([{'status': 'rejected', 'reason': None}]))
    archive = tmp_path / 'evidence.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        for path in source.iterdir():
            output.write(path, path.name)
    return archive, hashlib.sha256(archive.read_bytes()).hexdigest(), rows, selections


def test_preserves_outcomes_unknowns_and_recorded_text(tmp_path):
    archive, digest, rows, selections = bundle(tmp_path)
    result = export_archive(archive, digest)
    assert result['worlds'] == rows
    assert result['selections'] == selections
    assert result['supporting_records']['investigator-traces.json'] == [{'status': 'rejected', 'reason': None}]
    assert result['plans'][0]['verdict']['verdict'] == 'reproduced_regression'
    assert result['provenance']['new_model_calls'] == 0


def test_rejects_wrong_authentication(tmp_path):
    archive, _, _, _ = bundle(tmp_path)
    with pytest.raises(IntegrityError, match='authentication'):
        export_archive(archive, '0' * 64)


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'back\\slash'])
def test_rejects_unsafe_entries_even_with_matching_digest(tmp_path, name):
    archive = tmp_path / 'unsafe.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr(name, 'unsafe')
    with pytest.raises(IntegrityError, match='Unsafe archive entry'):
        export_archive(archive, hashlib.sha256(archive.read_bytes()).hexdigest())
