import copy
import json
import time
import unittest
from unittest.mock import patch

from preflight.service_executor import admit, endpoint, health_request, _raw_health_request
from preflight.isolated_executor import container_flags, inspect_container, ExecutionError
from preflight.petclinic_adapter import AdmissionError, digest
from preflight_tests.test_execution_manifest import configured


def stalled_worker(*args):
    time.sleep(10)


def service_config():
    m, d = configured()
    m['dependencies'], m['observers'] = [], []
    m['projects'][0]['service']['environment_bindings'] = []
    p = {'schema': 'wheel-service-execution-policy-v1', 'manifest_sha256': digest(m),
         'allowed_images': [m['projects'][0]['image']], 'max_repetitions': 2, 'total_timeout_seconds': 300}
    return m, d, p


class ServiceExecutorTests(unittest.TestCase):
    def test_admission_is_bound_and_capability_limited(self):
        m, d, p = service_config()
        admit(m, d, p, 2)
        m['projects'][0]['service']['health']['path'] = '/changed'
        with self.assertRaises(AdmissionError):
            admit(m, d, p, 1)
        m, d = configured()
        _, _, p = service_config()
        p['manifest_sha256'] = digest(m)
        with self.assertRaisesRegex(AdmissionError, 'stateless HTTP'):
            admit(m, d, p, 1)

    def test_service_flags_mount_source_read_only_on_named_network(self):
        m, _, _ = service_config()
        flags = container_flags(m, 'api', 'work', network='world-net', readonly_work=True)
        self.assertEqual(flags[flags.index('--network') + 1], 'world-net')
        self.assertIn('type=volume,src=work,dst=/work,readonly', flags)
        self.assertNotIn('/input/source.tar.gz', ' '.join(flags))

    def test_host_probe_restricts_endpoint_to_own_internal_network(self):
        net = {'Internal': True, 'Name': 'world', 'IPAM': {'Config': [{'Subnet': '172.19.0.0/16'}]}}
        service = {'NetworkSettings': {'Networks': {'world': {'IPAddress': '172.19.0.2'}}}, 'HostConfig': {'PortBindings': {}}}
        with patch('preflight.service_executor.checked', side_effect=[json.dumps([net]), json.dumps([service])]):
            self.assertEqual(endpoint('api', 'world'), '172.19.0.2')
        for change in [lambda n, s: n.update(Internal=False),
                       lambda n, s: s['NetworkSettings']['Networks']['world'].update(IPAddress='8.8.8.8'),
                       lambda n, s: s['HostConfig'].update(PortBindings={'8080/tcp': [{}]})]:
            n, s = copy.deepcopy(net), copy.deepcopy(service)
            change(n, s)
            with patch('preflight.service_executor.checked', side_effect=[json.dumps([n]), json.dumps([s])]), self.assertRaises(ExecutionError):
                endpoint('api', 'world')

    def test_health_does_not_follow_redirect_or_send_credentials(self):
        with patch('preflight.service_executor.http.client.HTTPConnection') as factory:
            connection = factory.return_value
            response = connection.getresponse.return_value
            response.status = 302
            response.read.return_value = b'redirect'
            result = _raw_health_request('172.19.0.2', 8080, '/health', 1)
            self.assertEqual(result['status'], 302)
            connection.request.assert_called_once_with('GET', '/health', headers={'Connection': 'close'})
            connection.close.assert_called_once()

    def test_oversized_health_response_rejected(self):
        with patch('preflight.service_executor.http.client.HTTPConnection') as factory:
            factory.return_value.getresponse.return_value.read.return_value = b'x' * 65537
            with self.assertRaises(ExecutionError):
                _raw_health_request('172.19.0.2', 8080, '/health', 1)

    def test_health_worker_hard_deadline_terminates_stalled_transport(self):
        with patch('preflight.service_executor._health_worker', stalled_worker):
            started = time.monotonic()
            result = health_request('172.19.0.2', 8080, '/health', 0.05)
            self.assertEqual(result['error_type'], 'HealthDeadlineExceeded')
            self.assertLess(time.monotonic() - started, 2)
