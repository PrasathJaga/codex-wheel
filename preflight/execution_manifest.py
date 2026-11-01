"""Validate shared Java/Python execution configuration. This module never runs it."""
import argparse
import copy
import json
from pathlib import Path
import re

from preflight.petclinic_adapter import AdmissionError, digest, exact
from preflight.petclinic_evaluation import strict_json

SCHEMA = 'wheel-execution-manifest-v1'
IDENTIFIER = r'[a-z][a-z0-9_]{0,47}'
IMAGE = r'[a-z0-9][a-z0-9./:_-]{0,199}@sha256:[0-9a-f]{64}'
PROGRAMS = frozenset({'mvn', './mvnw', 'gradle', './gradlew', 'java', 'python', 'python3'})


def text(value, maximum=256):
    if type(value) is not str or not 1 <= len(value) <= maximum or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise AdmissionError('Bounded nonempty text required')
    return value


def identifier(value):
    if type(value) is not str or not re.fullmatch(IDENTIFIER, value):
        raise AdmissionError('Invalid identifier')
    return value


def integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise AdmissionError('Integer outside configuration bounds')


def path(value, allow_root=False):
    text(value)
    if allow_root and value == '.':
        return value
    if value.startswith('/') or '\\' in value or any(p in ('', '.', '..') for p in value.split('/')):
        raise AdmissionError('Repository-relative path required')
    return value


def sequence(value, maximum, minimum=0):
    if type(value) is not list or not minimum <= len(value) <= maximum:
        raise AdmissionError('List outside configuration bounds')
    return value


def image(value):
    if type(value) is not str or not re.fullmatch(IMAGE, value):
        raise AdmissionError('Immutable image digest required')


def commands(value, required):
    for command in sequence(value, 8, int(required)):
        exact(command, {'argv', 'timeout_seconds'})
        argv = sequence(command['argv'], 64, 1)
        for arg in argv:
            text(arg, 2048)
        if argv[0] not in PROGRAMS:
            raise AdmissionError('Unsupported command program')
        integer(command['timeout_seconds'], 1, 900)


def validate_manifest(manifest, discovery):
    """Shape/reference validation, not a safety approval or execution admission.

    Command arguments and repository wrappers remain untrusted executable code.
    Binding configuration to discovery hashes is not proof of provenance/review.
    """
    exact(manifest, {'schema', 'discovery_sha256', 'projects', 'dependencies', 'observers',
                     'limits', 'network', 'reset'})
    if manifest['schema'] != SCHEMA or discovery.get('schema') != 'wheel-project-discovery-v1':
        raise AdmissionError('Unsupported configuration version')
    if manifest['discovery_sha256'] != digest(discovery):
        raise AdmissionError('Discovery identity mismatch')
    if any(discovery[side]['status'] != 'recognized_requires_configuration' for side in ('baseline', 'candidate')):
        raise AdmissionError('Both revisions require recognized, valid project metadata')
    if manifest['network'] != {'build': 'reviewed_dependency_fetch_only', 'runtime': 'internal_only'}:
        raise AdmissionError('Unsupported network policy')
    if manifest['reset'] != 'fresh_environment_per_world':
        raise AdmissionError('Fresh reset required')
    limits = manifest['limits']
    exact(limits, {'cpu_millis', 'memory_mb', 'pids', 'world_timeout_seconds'})
    for key, low, high in [('cpu_millis', 100, 8000), ('memory_mb', 128, 8192),
                           ('pids', 16, 512), ('world_timeout_seconds', 10, 900)]:
        integer(limits[key], low, high)
    dependencies = {}
    for dependency in sequence(manifest['dependencies'], 8):
        exact(dependency, {'id', 'kind', 'image', 'port', 'seed_files'})
        key = identifier(dependency['id'])
        if key in dependencies:
            raise AdmissionError('Duplicate dependency')
        if dependency['kind'] not in ('postgres', 'redis'):
            raise AdmissionError('Unsupported dependency kind')
        image(dependency['image'])
        integer(dependency['port'], 1, 65535)
        for seed in sequence(dependency['seed_files'], 16):
            path(seed)
        if len(set(dependency['seed_files'])) != len(dependency['seed_files']):
            raise AdmissionError('Duplicate seed path')
        dependencies[key] = dependency
    projects, roots = set(), set()
    for project in sequence(manifest['projects'], 8, 1):
        exact(project, {'id', 'root', 'language', 'image', 'build', 'test', 'service'})
        key = identifier(project['id'])
        root = path(project['root'], allow_root=True)
        language = project['language']
        if key in projects or (root, language) in roots:
            raise AdmissionError('Duplicate project selection')
        projects.add(key)
        roots.add((root, language))
        systems = {'java': {'maven', 'gradle'},
                   'python': {'python_pyproject', 'python_setup', 'python_dependencies_only'}}
        if type(language) is not str or language not in systems:
            raise AdmissionError('Unsupported language')
        for side in ('baseline', 'candidate'):
            if not any(p['root'] == root and p.get('build_system') in systems[language]
                       for p in discovery[side]['projects']):
                raise AdmissionError('Selected root/language not present in both revisions')
        image(project['image'])
        commands(project['build'], required=False)
        commands(project['test'], required=True)
        service = project['service']
        if service is not None:
            exact(service, {'start', 'port', 'health', 'environment_bindings'})
            commands([service['start']], required=True)
            integer(service['port'], 1, 65535)
            health = service['health']
            exact(health, {'path', 'status', 'timeout_seconds'})
            text(health['path'])
            if (not health['path'].startswith('/') or health['path'].startswith('//')
                    or any(c in health['path'] for c in ('\\', '%', '?', '#'))
                    or any(p in ('.', '..') for p in health['path'].split('/'))):
                raise AdmissionError('Internal health path required')
            integer(health['status'], 200, 299)
            integer(health['timeout_seconds'], 1, 120)
            variables = set()
            for binding in sequence(service['environment_bindings'], 32):
                exact(binding, {'variable', 'dependency', 'field'})
                variable = binding['variable']
                if type(variable) is not str or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}', variable):
                    raise AdmissionError('Invalid environment variable name')
                identifier(binding['dependency'])
                if variable in variables or binding['dependency'] not in dependencies:
                    raise AdmissionError('Duplicate variable or unresolved dependency')
                variables.add(variable)
                if binding['field'] not in ('host', 'port', 'database', 'username', 'ephemeral_password'):
                    raise AdmissionError('Only disposable dependency bindings are supported')
    observers = set()
    for observer in sequence(manifest['observers'], 16):
        exact(observer, {'id', 'kind', 'dependency', 'tables', 'row_limit'})
        key = identifier(observer['id'])
        if key in observers:
            raise AdmissionError('Duplicate observer')
        observers.add(key)
        identifier(observer['dependency'])
        if (observer['kind'] != 'postgres_read_only_snapshot' or observer['dependency'] not in dependencies
                or dependencies[observer['dependency']]['kind'] != 'postgres'):
            raise AdmissionError('Unsupported or unresolved read-only observer')
        for table in sequence(observer['tables'], 16, 1):
            identifier(table)
        if len(set(observer['tables'])) != len(observer['tables']):
            raise AdmissionError('Duplicate observer table')
        integer(observer['row_limit'], 1, 10000)
    return {'schema': 'wheel-execution-configuration-review-v1', 'status': 'configuration_valid_requires_review',
            'manifest_sha256': digest(manifest), 'discovery_sha256': digest(discovery),
            'validated_manifest': copy.deepcopy(manifest), 'ready_for_execution': False,
            'commands_executed': 0, 'model_requests': 0,
            'blockers': ['generic_executor_not_implemented', 'trusted_image_command_and_network_review_required',
                         'seed_files_and_wrapper_paths_require_archive_content_validation',
                         'business_expectations_require_separate_approval',
                         'observer_permissions_and_state_reset_require_live_verification']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--discovery', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    # Limits apply before JSON parsing; duplicate keys are rejected.
    def read(p):
        with p.open('rb') as stream:
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise AdmissionError('Configuration input too large')
        return strict_json(raw.decode())
    result = validate_manifest(read(args.manifest), read(args.discovery))
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'ready_for_execution': False}))


if __name__ == '__main__':
    main()
