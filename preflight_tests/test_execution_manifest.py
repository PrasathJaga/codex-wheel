import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from preflight.execution_manifest import validate_manifest, main
from preflight.petclinic_adapter import AdmissionError, digest
from preflight.project_discovery import inspect_files


def configured(language='python'):
    source = ({'pyproject.toml': b'[project]\nname="message-api"', 'api.py': b'pass'} if language == 'python'
              else {'pom.xml': b'<project/>', 'src/Main.java': b'class Main {}'})
    discovery = {'schema': 'wheel-project-discovery-v1', 'baseline': inspect_files(source), 'candidate': inspect_files(source)}
    image = 'example.invalid/runtime@sha256:' + 'a' * 64
    command = {'argv': ['python', '-m', 'unittest'] if language == 'python' else ['mvn', '-B', 'verify'], 'timeout_seconds': 300}
    manifest = {'schema': 'wheel-execution-manifest-v1', 'discovery_sha256': digest(discovery),
                'projects': [{'id': 'api', 'root': '.', 'language': language, 'image': image,
                              'build': [], 'test': [command],
                              'service': {'start': {'argv': ['python', '-m', 'api'] if language == 'python' else ['java', '-jar', 'target/app.jar'], 'timeout_seconds': 120},
                                          'port': 8080, 'health': {'path': '/health', 'status': 200, 'timeout_seconds': 30},
                                          'environment_bindings': [{'variable': 'DB_HOST', 'dependency': 'db', 'field': 'host'}]}}],
                'dependencies': [{'id': 'db', 'kind': 'postgres', 'image': image, 'port': 5432, 'seed_files': ['fixtures/seed.sql']}],
                'observers': [{'id': 'rows', 'kind': 'postgres_read_only_snapshot', 'dependency': 'db', 'tables': ['records'], 'row_limit': 100}],
                'limits': {'cpu_millis': 2000, 'memory_mb': 2048, 'pids': 256, 'world_timeout_seconds': 300},
                'network': {'build': 'reviewed_dependency_fetch_only', 'runtime': 'internal_only'},
                'reset': 'fresh_environment_per_world'}
    return manifest, discovery


class ExecutionManifestTests(unittest.TestCase):
    def test_same_configuration_contract_for_java_and_python_never_executes(self):
        for language in ('java', 'python'):
            manifest, discovery = configured(language)
            with patch('subprocess.run', side_effect=AssertionError('Execution forbidden')):
                result = validate_manifest(manifest, discovery)
            self.assertEqual(result['status'], 'configuration_valid_requires_review')
            self.assertFalse(result['ready_for_execution'])
            self.assertEqual(result['commands_executed'], 0)
            self.assertEqual(result['manifest_sha256'], digest(manifest))

    def test_changed_discovery_and_missing_project_root_rejected(self):
        manifest, discovery = configured()
        changed = copy.deepcopy(discovery)
        changed['candidate']['source_identity_sha256'] = 'changed'
        with self.assertRaisesRegex(AdmissionError, 'identity mismatch'):
            validate_manifest(manifest, changed)
        manifest['projects'][0]['root'] = 'not-discovered'
        with self.assertRaisesRegex(AdmissionError, 'not present'):
            validate_manifest(manifest, discovery)

    def test_mutable_image_host_paths_shell_and_weakened_limits_rejected(self):
        changes = [lambda m: m['projects'][0].update(image='python:latest'),
                   lambda m: m['projects'][0].update(root='../host'),
                   lambda m: m['projects'][0]['test'][0].update(argv=['bash', '-c', 'echo bad']),
                   lambda m: m['limits'].update(memory_mb=True),
                   lambda m: m['limits'].update(pids=100000),
                   lambda m: m.update(reset='reuse_existing_database'),
                   lambda m: m['network'].update(runtime='host'),
                   lambda m: m['projects'][0]['service']['health'].update(path='//outside/health'),
                   lambda m: m['projects'][0]['service']['health'].update(path='/%2e%2e/host')]
        for change in changes:
            manifest, discovery = configured()
            change(manifest)
            with self.assertRaises(AdmissionError):
                validate_manifest(manifest, discovery)

    def test_unknown_fields_cannot_supply_answers_mounts_or_literal_credentials(self):
        for key, value in [('expected_verdict', 'fail'), ('repair_answer', 'healthy code'),
                           ('mounts', ['/host:/work']), ('environment', {'MODEL_API_KEY': 'literal'})]:
            manifest, discovery = configured()
            manifest[key] = value
            with self.assertRaises(AdmissionError):
                validate_manifest(manifest, discovery)
        manifest, discovery = configured()
        manifest['projects'][0]['service']['environment_bindings'][0]['value'] = 'literal password'
        with self.assertRaises(AdmissionError):
            validate_manifest(manifest, discovery)

    def test_dependency_and_observer_references_and_identifiers_rejected(self):
        changes = [lambda m: m['projects'][0]['service']['environment_bindings'][0].update(dependency='missing'),
                   lambda m: m['observers'][0].update(dependency='missing'),
                   lambda m: m['observers'][0].update(tables=['records; DROP TABLE records']),
                   lambda m: m['observers'][0].update(sql='SELECT 1'),
                   lambda m: m['dependencies'].append(copy.deepcopy(m['dependencies'][0])),
                   lambda m: m['projects'][0].update(test=[])]
        for change in changes:
            manifest, discovery = configured()
            change(manifest)
            with self.assertRaises(AdmissionError):
                validate_manifest(manifest, discovery)

    def test_duplicate_json_keys_rejected_by_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, discovery = configured()
            (root / 'manifest.json').write_text('{"schema":"one","schema":"two"}')
            (root / 'discovery.json').write_text(json.dumps(discovery))
            argv = ['manifest', '--manifest', str(root / 'manifest.json'), '--discovery', str(root / 'discovery.json'), '--output', str(root / 'result.json')]
            with patch('sys.argv', argv), self.assertRaises(AdmissionError):
                main()
            self.assertFalse((root / 'result.json').exists())

    def test_valid_cli_and_arguments_do_not_mean_command_safety_approval(self):
        manifest, discovery = configured()
        # A Python argument can execute arbitrary code inside a future sandbox.
        # This validator must never pretend argv-only configuration proves safety.
        manifest['projects'][0]['test'][0]['argv'] = ['python', '-c', 'raise RuntimeError("untrusted")']
        result = validate_manifest(manifest, discovery)
        self.assertIn('trusted_image_command_and_network_review_required', result['blockers'])
        self.assertFalse(result['ready_for_execution'])
        self.assertEqual(result['validated_manifest'], manifest)
        result['validated_manifest']['projects'].clear()
        self.assertEqual(len(manifest['projects']), 1)


if __name__ == '__main__':
    unittest.main()
