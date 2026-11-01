import copy
import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from preflight.isolated_executor import admit_policy, container_flags, inspect_container, start_container, docker, ExecutionError
from preflight.petclinic_adapter import AdmissionError, digest
from preflight_tests.test_execution_manifest import configured


def offline():
    manifest, discovery = configured()
    manifest['projects'][0]['service'] = None
    manifest['dependencies'] = []
    manifest['observers'] = []
    policy = {'schema': 'wheel-local-execution-policy-v1', 'manifest_sha256': digest(manifest),
              'allowed_images': [manifest['projects'][0]['image']], 'max_repetitions': 2, 'total_timeout_seconds': 300}
    return manifest, discovery, policy


class IsolatedExecutorTests(unittest.TestCase):
    def test_docker_environment_excludes_keys_and_host_configuration(self):
        original = subprocess.Popen
        seen = []
        def local_control(argv, **kwargs):
            seen.append((argv, kwargs['env']))
            self.assertEqual(set(kwargs['env']), {'PATH', 'LANG', 'DOCKER_CONFIG'})
            self.assertEqual(os.listdir(kwargs['env']['DOCKER_CONFIG']), [])
            return original([sys.executable, '-c', 'print("trusted control")'], **kwargs)
        with patch.dict(os.environ, {'MODEL_API_KEY': 'not-for-child', 'GITHUB_TOKEN': 'not-for-child'}), patch('preflight.isolated_executor.subprocess.Popen', side_effect=local_control):
            result = docker(['version'], 5)
        self.assertEqual(result['returncode'], 0)
        self.assertIn('trusted control', result['output'])
        self.assertEqual(seen[0][0], ['docker', 'version'])

    def test_output_limit_preserves_partial_control_output(self):
        original = subprocess.Popen
        def local_control(argv, **kwargs):
            return original([sys.executable, '-c', 'import sys;sys.stdout.write("x"*100000);sys.stdout.flush()'], **kwargs)
        with patch('preflight.isolated_executor.LOG_LIMIT', 65536), patch('preflight.isolated_executor.subprocess.Popen', side_effect=local_control):
            with self.assertRaises(ExecutionError) as caught:
                docker(['version'], 5)
        self.assertGreater(len(caught.exception.output), 0)
        self.assertLessEqual(len(caught.exception.output), 65536)

    def test_policy_binds_full_commands_and_images(self):
        m, d, p = offline()
        admit_policy(m, d, p, 2)
        changed = copy.deepcopy(m)
        changed['projects'][0]['test'][0]['argv'].append('different')
        with self.assertRaisesRegex(AdmissionError, 'changed manifest'):
            admit_policy(changed, d, p, 1)
        p['allowed_images'] = ['other.invalid/runtime@sha256:' + 'b' * 64]
        with self.assertRaisesRegex(AdmissionError, 'trusted execution policy'):
            admit_policy(m, d, p, 1)

    def test_services_dependencies_and_repeat_budget_unsupported(self):
        m, d = configured()
        p = {'schema': 'wheel-local-execution-policy-v1', 'manifest_sha256': digest(m),
             'allowed_images': [m['projects'][0]['image']], 'max_repetitions': 2, 'total_timeout_seconds': 300}
        with self.assertRaisesRegex(AdmissionError, 'offline build/test'):
            admit_policy(m, d, p, 1)
        m, d, p = offline()
        with self.assertRaises(AdmissionError):
            admit_policy(m, d, p, 3)

    def test_flags_have_no_host_checkout_or_credentials(self):
        m, _, _ = offline()
        flags = container_flags(m, 'container', 'disposable-volume')
        self.assertEqual(flags[flags.index('--network') + 1], 'none')
        self.assertIn('--read-only', flags)
        self.assertNotIn('type=bind', ' '.join(flags))
        self.assertNotIn('MODEL_API_KEY', ' '.join(flags))
        self.assertNotIn('/var/run/docker.sock', ' '.join(flags))
        self.assertIn('1000:1000', flags)

    def test_inspection_rejects_host_mount_and_weakened_root(self):
        valid = {'HostConfig': {'NetworkMode': 'none', 'ReadonlyRootfs': True, 'Privileged': False,
                 'Binds': None, 'Mounts': [{'Type': 'volume', 'Source': 'work', 'Target': '/work', 'ReadOnly': False}],
                 'CapAdd': None, 'CapDrop': ['ALL'], 'SecurityOpt': ['no-new-privileges']},
                 'Config': {'User': '1000:1000'}}
        with patch('preflight.isolated_executor.checked', return_value=json.dumps([valid])):
            self.assertEqual(inspect_container('c', 'work')['network'], 'none')
        for change in [lambda x: x['HostConfig'].update(ReadonlyRootfs=False),
                       lambda x: x['HostConfig']['Mounts'].append({'Type':'bind','Source':'/host','Target':'/private'}),
                       lambda x: x['HostConfig'].update(NetworkMode='host')]:
            bad = copy.deepcopy(valid)
            change(bad)
            with patch('preflight.isolated_executor.checked', return_value=json.dumps([bad])), self.assertRaises(ExecutionError):
                inspect_container('c', 'work')

    def test_container_exit_code_checked_independently_of_cli_success(self):
        state = {'Running': False, 'Status': 'exited', 'ExitCode': 7, 'OOMKilled': False}
        with patch('preflight.isolated_executor.docker', return_value={'returncode': 0, 'output':'failed test'}), patch('preflight.isolated_executor.checked', return_value=json.dumps(state)):
            self.assertEqual(start_container('c', 5)['returncode'], 7)
        state['OOMKilled'] = True
        with patch('preflight.isolated_executor.docker', return_value={'returncode': 0, 'output':'before OOM'}), patch('preflight.isolated_executor.checked', return_value=json.dumps(state)), self.assertRaises(ExecutionError):
            start_container('c', 5)


if __name__ == '__main__':
    unittest.main()
