import copy
import hashlib
import unittest
from preflight.dependency_environment import admit_bundle
from preflight.isolated_executor import container_flags
from preflight.petclinic_adapter import AdmissionError, digest
from preflight.petclinic_source_intake import normalized_archive
from preflight_tests.test_isolated_executor import offline


def configuration():
    manifest, discovery, policy = offline()
    raw = b'opaque package control, never imported on host'
    destination = 'python/wheels/control-1.0-py3-none-any.whl'
    lock = {'schema':'wheel-dependency-lock-v1', 'discovery_sha256':digest(discovery),
            'purpose':'authored_acquisition_control', 'artifacts':[{'kind':'python_wheel',
            'url':'https://files.pythonhosted.org/packages/control-1.0-py3-none-any.whl',
            'sha256':hashlib.sha256(raw).hexdigest(), 'size_bytes':len(raw), 'destination':destination}]}
    acquisition = {'schema':'wheel-dependency-acquisition-policy-v1', 'lock_sha256':digest(lock),
                   'allowed_urls':[lock['artifacts'][0]['url']], 'total_timeout_seconds':30, 'artifact_timeout_seconds':10}
    archive = normalized_archive({destination:raw})
    policy.update(schema='wheel-dependency-execution-policy-v1', dependency_lock_sha256=digest(lock),
                  dependency_bundle_sha256=hashlib.sha256(archive).hexdigest())
    return manifest, discovery, policy, {'archive':archive, 'lock':lock, 'acquisition_policy':acquisition}, destination


class DependencyEnvironmentTests(unittest.TestCase):
    def test_valid_bundle_is_data_and_source_discovery_is_unchanged(self):
        m,d,p,b,_=configuration()
        before=copy.deepcopy(d)
        self.assertEqual(admit_bundle(m,d,p,1,b),b['archive'])
        self.assertEqual(d,before)

    def test_bundle_and_lock_bind_current_execution(self):
        for target in ('bundle','lock','discovery'):
            m,d,p,b,_=configuration()
            if target=='bundle': b['archive']+=b'changed'
            elif target=='lock': p['dependency_lock_sha256']='0'*64
            else: b['lock']['discovery_sha256']='0'*64; b['acquisition_policy']['lock_sha256']=digest(b['lock']);p['dependency_lock_sha256']=digest(b['lock'])
            with self.assertRaises(AdmissionError):admit_bundle(m,d,p,1,b)

    def test_rehashed_archive_cannot_smuggle_missing_extra_or_changed_artifacts(self):
        for files in ({},{'extra.whl':b'extra'},{'python/wheels/control-1.0-py3-none-any.whl':b'altered'}):
            m,d,p,b,_=configuration()
            b['archive']=normalized_archive(files);p['dependency_bundle_sha256']=hashlib.sha256(b['archive']).hexdigest()
            with self.assertRaises(AdmissionError):admit_bundle(m,d,p,1,b)

    def test_bundle_mounted_read_only_without_network_or_source_directory_bind(self):
        m,_,_,_,_=configuration()
        flags=container_flags(m,'container','source-work',dependency_volume='reviewed-dependencies')
        self.assertIn('type=volume,src=reviewed-dependencies,dst=/dependencies,readonly',flags)
        self.assertEqual(flags[flags.index('--network')+1],'none')
        self.assertNotIn('type=bind',' '.join(flags))


if __name__=='__main__':unittest.main()
