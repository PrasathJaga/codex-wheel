"""Versioned, recorded evidence contract. No inference or execution is performed."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import tempfile
import zipfile

from wheel.plan_guard import IntegrityError
from wheel.report_visualizer import inspect, read


def export_archive(archive, expected_sha256):
    """The digest must come from an independently trusted evidence index."""
    archive = Path(archive)
    if archive.is_symlink() or archive.stat().st_size > 64 * 1024 * 1024:
        raise IntegrityError('Unsafe archive')
    raw = archive.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise IntegrityError('Archive authentication failed')
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
            entries = bundle.infolist()
            names = [entry.filename for entry in entries]
            if len(names) != len(set(names)) or len(names) > 4096:
                raise IntegrityError('Duplicate or excessive archive entries')
            if sum(entry.file_size for entry in entries) > 128 * 1024 * 1024:
                raise IntegrityError('Expanded archive exceeds bound')
            for entry in entries:
                path = PurePosixPath(entry.filename)
                if (path.is_absolute() or '..' in path.parts or '\\' in entry.filename
                        or stat.S_ISLNK(entry.external_attr >> 16)):
                    raise IntegrityError('Unsafe archive entry')
            bundle.extractall(root)
        plan_hash = hashlib.sha256(read(root, 'locked-comparison.json')).hexdigest()
        frozen, groups = inspect(root, plan_hash)
        # Preserve raw records, including errors, unknown fields and recorded text.
        # Consumers must not infer fresh model activity from the presence of text.
        records = json.loads(read(root, 'results.json'))
        selections = frozen.get('selections', frozen.get('selection'))
        if (root / 'selections.json').exists():
            selections = json.loads(read(root, 'selections.json'))
        return {
            'schema_version': 'codex-wheel.evidence.v1',
            'provenance': {'archive_sha256': expected_sha256, 'plan_sha256': plan_hash,
                           'activity': 'recorded_evidence_only', 'new_model_calls': 0},
            'frozen': frozen,
            'selections': selections,
            'plans': [{'id': plan['id'], 'verdict': outcome} for plan, _, outcome in groups],
            'worlds': records,
            'limits': ['Supported archived paired experiments only; not a fresh execution.',
                       'No production frequency, financial saving or general repair claim.'],
        }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = export_archive(args.archive, args.sha256)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
