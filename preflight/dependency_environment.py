"""Verify reviewed dependency bundles for offline container consumption; no installs."""
import hashlib

from preflight.dependency_bundle import validate
from preflight.isolated_executor import admit_policy
from preflight.petclinic_adapter import AdmissionError, digest, exact
from preflight.petclinic_source_intake import collect_archive, normalized_archive


def admit_bundle(manifest, discovery, policy, repetitions, dependency):
    exact(dependency, {'archive', 'lock', 'acquisition_policy'})
    exact(policy, {'schema', 'manifest_sha256', 'allowed_images', 'max_repetitions', 'total_timeout_seconds',
                   'dependency_lock_sha256', 'dependency_bundle_sha256'})
    if policy['schema'] != 'wheel-dependency-execution-policy-v1':
        raise AdmissionError('Unsupported dependency execution policy')
    # Existing offline admission stays unchanged; extra commitments are checked here.
    offline = {k: policy[k] for k in ('manifest_sha256', 'allowed_images', 'max_repetitions', 'total_timeout_seconds')}
    offline['schema'] = 'wheel-local-execution-policy-v1'
    admit_policy(manifest, discovery, offline, repetitions)
    lock = dependency['lock']
    validate(lock, dependency['acquisition_policy'])
    if lock['discovery_sha256'] != digest(discovery) or policy['dependency_lock_sha256'] != digest(lock):
        raise AdmissionError('Dependency lock not bound to current discovery/policy')
    files = collect_archive(dependency['archive'], policy['dependency_bundle_sha256'], 'admitted')
    expected = {a['destination']: a for a in lock['artifacts']}
    if set(files) != set(expected):
        raise AdmissionError('Missing or extra dependency files')
    for path, raw in files.items():
        if len(raw) != expected[path]['size_bytes'] or hashlib.sha256(raw).hexdigest() != expected[path]['sha256']:
            raise AdmissionError('Dependency artifact bytes changed')
    return normalized_archive(files)
