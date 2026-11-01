import copy
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from preflight.dependency_bundle import validate, acquire, PinnedHTTPSConnection, fetch
from preflight.petclinic_adapter import AdmissionError, digest
from preflight.petclinic_source_intake import collect_archive


def stalled_worker(*args):
    time.sleep(10)


def configured():
    raw = b'opaque artifact control'
    url = 'https://files.pythonhosted.org/packages/control/demo-1.0-py3-none-any.whl'
    lock = {'schema':'wheel-dependency-lock-v1','discovery_sha256':'a'*64,'purpose':'authored_acquisition_control',
            'artifacts':[{'kind':'python_wheel','url':url,'sha256':hashlib.sha256(raw).hexdigest(),
                          'size_bytes':len(raw),'destination':'python/wheels/demo-1.0-py3-none-any.whl'}]}
    policy = {'schema':'wheel-dependency-acquisition-policy-v1','lock_sha256':digest(lock),
              'allowed_urls':[url],'total_timeout_seconds':30,'artifact_timeout_seconds':10}
    return lock,policy,raw


class DependencyBundleTests(unittest.TestCase):
    def test_verified_bytes_pack_deterministically_without_execution(self):
        lock,policy,raw=configured()
        with tempfile.TemporaryDirectory() as tmp:
            bundles=[]
            with patch('subprocess.run',side_effect=AssertionError('project execution forbidden')):
                for i in range(2):
                    out=Path(tmp)/str(i)
                    result=acquire(lock,policy,out,fetcher=lambda *a:raw)
                    self.assertEqual(result['status'],'artifacts_verified')
                    self.assertFalse(result['packages_installed'])
                    self.assertFalse(result['dependency_closure_verified'])
                    bundle=(out/'dependencies.tar.gz').read_bytes()
                    files=collect_archive(bundle,result['bundle_sha256'],'admitted')
                    self.assertEqual(files,{lock['artifacts'][0]['destination']:raw})
                    bundles.append(bundle)
            self.assertEqual(bundles[0],bundles[1])

    def test_mismatch_is_preserved_and_never_retried(self):
        lock,policy,raw=configured()
        with tempfile.TemporaryDirectory() as tmp:
            with patch('preflight.dependency_bundle.fetch') as unused:
                calls=[]
                def bad(*args):calls.append(args);return b'wrong bytes'
                result=acquire(lock,policy,Path(tmp)/'out',fetcher=bad)
                self.assertEqual(len(calls),1)
                self.assertEqual(result['status'],'acquisition_failed')
                self.assertEqual(result['artifacts'][0]['status'],'failed')
                self.assertIsNone(result['bundle_sha256'])
                self.assertFalse((Path(tmp)/'out/dependencies.tar.gz').exists())

    def test_network_failure_keeps_prior_receipt_and_stops_following_artifacts(self):
        lock,policy,raw=configured()
        second={'kind':'maven_artifact','url':'https://repo.maven.apache.org/maven2/a/b/1/b-1.jar',
                'destination':'maven/repository/a/b/1/b-1.jar','sha256':'b'*64,'size_bytes':1}
        lock['artifacts'].append(second)
        policy['allowed_urls'].append(second['url']);policy['lock_sha256']=digest(lock)
        calls=[]
        def fetcher(*args):
            calls.append(args)
            if len(calls)==2:raise OSError('unavailable')
            return raw
        with tempfile.TemporaryDirectory() as tmp:
            result=acquire(lock,policy,Path(tmp)/'out',fetcher=fetcher)
            self.assertEqual([a['status'] for a in result['artifacts']],['verified','failed'])
            self.assertEqual(result['status'],'acquisition_failed')

    def test_changed_lock_unknown_origin_redirect_query_credentials_and_traversal_rejected(self):
        mutations=[lambda a:a.update(url='https://user:pass@files.pythonhosted.org/demo.whl'),
                   lambda a:a.update(url='https://localhost/demo.whl'),
                   lambda a:a.update(url='http://files.pythonhosted.org/demo.whl'),
                   lambda a:a.update(url=a['url']+'?token=secret'),
                   lambda a:a.update(destination='../wheel.whl'),
                   lambda a:a.update(destination='python/wheels/other.whl'),
                   lambda a:a.update(size_bytes=True),
                   lambda a:a.update(kind='python_source_distribution')]
        for mutation in mutations:
            lock,policy,_=configured();mutation(lock['artifacts'][0]);policy['lock_sha256']=digest(lock)
            with self.assertRaises(AdmissionError):validate(lock,policy)
        lock,policy,_=configured();lock['purpose']='execution_dependencies'
        with self.assertRaisesRegex(AdmissionError,'lock changed'):validate(lock,policy)

    def test_private_dns_answers_rejected_before_connecting(self):
        connection=PinnedHTTPSConnection('files.pythonhosted.org',timeout=1)
        with patch('socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]),patch('socket.create_connection') as connect:
            with self.assertRaisesRegex(AdmissionError,'public addresses'):connection.connect()
            connect.assert_not_called()

    def test_valid_dns_connects_to_pinned_ip_with_original_tls_hostname(self):
        connection=PinnedHTTPSConnection('files.pythonhosted.org',timeout=1)
        with patch('socket.getaddrinfo',return_value=[(2,1,6,'',('151.101.0.223',443))]),patch('socket.create_connection') as connect,patch('ssl.create_default_context') as context:
            connection.connect()
            connect.assert_called_once_with(('151.101.0.223',443),1)
            context.return_value.wrap_socket.assert_called_once_with(connect.return_value,server_hostname='files.pythonhosted.org')

    def test_destination_collisions_and_oversized_budgets_rejected(self):
        lock,policy,_=configured();lock['artifacts'].append(copy.deepcopy(lock['artifacts'][0]));policy['lock_sha256']=digest(lock)
        with self.assertRaises(AdmissionError):validate(lock,policy)
        lock,policy,_=configured();policy['total_timeout_seconds']=10000
        with self.assertRaises(AdmissionError):validate(lock,policy)

    def test_stalled_download_worker_is_terminated_at_deadline(self):
        with patch('preflight.dependency_bundle._download_worker',stalled_worker):
            start=time.monotonic()
            with self.assertRaisesRegex(AdmissionError,'hard deadline'):
                fetch('https://files.pythonhosted.org/control.whl',1,0.05)
            self.assertLess(time.monotonic()-start,2)
