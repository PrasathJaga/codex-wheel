import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from preflight.petclinic_adapter import AdmissionError
from preflight.project_discovery import discover_pair, inspect_files


def archive(files, root='repo', link=None):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as tar:
        for path, content in files.items():
            item = tarfile.TarInfo(root + '/' + path)
            item.size = len(content)
            tar.addfile(item, io.BytesIO(content))
        if link:
            item = tarfile.TarInfo(root + '/alias')
            item.type = tarfile.SYMTYPE
            item.linkname = link
            tar.addfile(item)
    return stream.getvalue()


def pair(a, b):
    return discover_pair(a, b, hashlib.sha256(a).hexdigest(), hashlib.sha256(b).hexdigest(), 'repo', 'repo')


class DiscoveryTests(unittest.TestCase):
    def test_namespaced_maven_and_python_multiroot_without_domain_fixtures(self):
        files = {'catalog/pom.xml': b'<project xmlns="http://maven.apache.org/POM/4.0.0"><modules><module>api</module></modules></project>',
                 'catalog/src/Catalog.java': b'class Catalog {}',
                 'worker/pyproject.toml': b'[project]\nname="queue-worker"\nrequires-python=">=3.11"\n[build-system]\nbuild-backend="setuptools.build_meta"',
                 'worker/worker.py': b'raise RuntimeError("MUST NOT EXECUTE")'}
        report = pair(archive(files), archive(files))
        self.assertEqual(report['changes'], [])
        self.assertEqual(report['baseline']['source_file_counts'], {'java': 1, 'python': 1})
        self.assertEqual(report['baseline']['projects'][0]['declared_modules'], ['api'])
        self.assertIn('multiple_project_roots_require_explicit_selection', report['baseline']['blockers'])
        self.assertFalse(report['generic_execution_supported'])

    def test_all_changed_paths_including_tests_manifests_and_deleted_sources(self):
        a = archive({'pom.xml': b'<project/>', 'src/A.java': b'class A {}', 'test.py': b'assert True'})
        b = archive({'pom.xml': b'<project><name>new</name></project>', 'test.py': b'assert False', 'new.py': b'x=1'})
        changes = {v['path']: v for v in pair(a, b)['changes']}
        self.assertEqual(changes['src/A.java']['kind'], 'deleted')
        self.assertEqual(changes['new.py']['kind'], 'added')
        self.assertEqual(changes['test.py']['kind'], 'modified')
        self.assertEqual(changes['pom.xml']['kind'], 'modified')

    def test_setup_and_gradle_are_not_executed_or_declared_ready(self):
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp) / 'executed'
            source = ('from pathlib import Path\nPath(' + repr(str(marker)) + ').write_text("BAD")').encode()
            with patch('subprocess.run', side_effect=AssertionError('No subprocess allowed')):
                r = inspect_files({'setup.py': source, 'build.gradle': b'throw new Exception()', 'app.py': source})
            self.assertFalse(marker.exists())
            self.assertTrue(all(p['status'] == 'requires_configuration' for p in r['projects']))
            self.assertFalse(r['ready_for_execution'])

    def test_invalid_xml_and_toml_are_explicit(self):
        for path, source in [('pom.xml', b'<project>'), ('pyproject.toml', b'[project'),
                             ('pom.xml', b'<!DOCTYPE project [<!ENTITY x "a">]><project>&x;</project>'),
                             ('pyproject.toml', b'[project]\nrequires-python=4')]:
            report = inspect_files({path: source, 'a.py': b'pass'})
            self.assertEqual(report['status'], 'invalid_project_metadata')

    def test_unsupported_and_ignored_build_output(self):
        report = inspect_files({'README.md': b'hello', 'target/A.java': b'generated', '.venv/a.py': b'pass'})
        self.assertEqual(report['status'], 'unsupported_project')
        self.assertEqual(report['source_file_counts'], {'java': 0, 'python': 0})

    def test_archive_digest_and_links_fail_closed(self):
        raw = archive({'app.py': b'pass'})
        with self.assertRaises(AdmissionError):
            discover_pair(raw, raw, '0' * 64, hashlib.sha256(raw).hexdigest(), 'repo', 'repo')
        with self.assertRaises(AdmissionError):
            pair(raw, archive({'app.py': b'pass'}, link='/outside'))
        with self.assertRaises(AdmissionError):
            pair(raw, archive({'../outside': b'pass'}))

    def test_deterministic_identity_and_metadata_only_change(self):
        a = archive({'pyproject.toml': b'[project]\nname="a"', 'main.py': b'pass'})
        b = archive({'pyproject.toml': b'[project]\nname="b"', 'main.py': b'pass'})
        self.assertEqual(pair(a, b), pair(a, b))
        self.assertNotEqual(pair(a, b)['baseline']['source_identity_sha256'], pair(a, b)['candidate']['source_identity_sha256'])

    @unittest.skipUnless(os.environ.get('WHEEL_PILOT_ARCHIVE'), 'public source archive not supplied')
    def test_actual_public_project_discovery_without_fixture_path_allowlist(self):
        raw = Path(os.environ['WHEEL_PILOT_ARCHIVE']).read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        root = 'spring-petclinic-rest-e1987d2b4715b30f8b97050b3a399fdcadf92cb3'
        report = discover_pair(raw, raw, sha, sha, root, root)
        self.assertEqual(report['baseline']['status'], 'recognized_requires_configuration')
        self.assertGreater(report['baseline']['source_file_counts']['java'], 0)
        self.assertFalse(report['project_code_executed'])
        self.assertEqual(report['model_requests'], 0)


if __name__ == '__main__':
    unittest.main()
