"""Bounded, read-only Java/Python discovery from authenticated source archives.

No project imports, build commands, wrappers, plugins or model requests are run.
Recognition is not execution admission or a behavioral verification result.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tomllib
import xml.etree.ElementTree as ET

from preflight.petclinic_adapter import digest
# Reuse the already exercised domain-neutral archive checks, unchanged. This
# collector has no PetClinic source/path allowlist or project execution behavior.
from preflight.petclinic_source_intake import collect_archive

IGNORED_PARTS = frozenset({'.git', '.venv', 'venv', '__pycache__', 'node_modules', 'target', 'build'})
MANIFESTS = frozenset({'pom.xml', 'build.gradle', 'build.gradle.kts', 'pyproject.toml',
                       'setup.py', 'setup.cfg', 'requirements.txt'})
MAX_METADATA = 1024 * 1024


def _metadata(name, data):
    """Only declarative, literal facts. Never evaluate build/property expressions."""
    if len(data) > MAX_METADATA:
        return {'status': 'invalid_metadata', 'reason': 'metadata_size_limit'}
    try:
        text = data.decode('utf-8')
        if name == 'pom.xml':
            if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
                return {'status': 'invalid_metadata', 'reason': 'xml_declarations_forbidden'}
            root = ET.fromstring(text)
            if root.tag.split('}')[-1] != 'project':
                return {'status': 'invalid_metadata', 'reason': 'not_maven_project'}
            namespace = root.tag[:-len('project')]
            modules = [node.text.strip() for node in root.findall(namespace + 'modules/' + namespace + 'module')
                       if node.text and node.text.strip()]
            return {'status': 'recognized', 'build_system': 'maven', 'declared_modules': modules,
                    'modules_resolved': False, 'build_extensions_evaluated': False}
        if name == 'pyproject.toml':
            value = tomllib.loads(text)
            build = value.get('build-system', {})
            project = value.get('project', {})
            if type(build) is not dict or type(project) is not dict:
                return {'status': 'invalid_metadata', 'reason': 'metadata_table_expected'}
            requires = project.get('requires-python')
            backend = build.get('build-backend')
            if any(v is not None and type(v) is not str for v in (requires, backend)):
                return {'status': 'invalid_metadata', 'reason': 'metadata_string_expected'}
            return {'status': 'recognized', 'build_system': 'python_pyproject',
                    'declared_requires_python': requires, 'declared_build_backend': backend,
                    'metadata_executed': False, 'test_runner_inferred': False}
        return {'status': 'requires_configuration', 'build_system': {
            'build.gradle': 'gradle', 'build.gradle.kts': 'gradle', 'setup.py': 'python_setup',
            'setup.cfg': 'python_setup', 'requirements.txt': 'python_dependencies_only'}[name],
                'reason': 'not_evaluated_or_sufficient_for_execution'}
    except (UnicodeError, ET.ParseError, tomllib.TOMLDecodeError):
        return {'status': 'invalid_metadata', 'reason': 'malformed_metadata'}


def inspect_files(files):
    active = {p: data for p, data in files.items() if not IGNORED_PARTS.intersection(PurePosixPath(p).parts)}
    counts = {language: sum(p.endswith(suffix) for p in active)
              for language, suffix in [('java', '.java'), ('python', '.py')]}
    projects = []
    for path, data in sorted(active.items()):
        name = PurePosixPath(path).name
        if name in MANIFESTS:
            projects.append({'root': str(PurePosixPath(path).parent), 'manifest': path,
                             'manifest_sha256': hashlib.sha256(data).hexdigest(), **_metadata(name, data)})
    invalid = any(p['status'] == 'invalid_metadata' for p in projects)
    status = 'invalid_project_metadata' if invalid else (
        'recognized_requires_configuration' if projects and any(counts.values()) else 'unsupported_project')
    blockers = ['sandbox_execution_not_implemented_for_generic_projects',
                'explicit_build_test_and_service_configuration_required',
                'declared_business_expectations_and_observers_required',
                'runtime_dependency_and_network_policy_required']
    if len({p['root'] for p in projects}) > 1:
        blockers.append('multiple_project_roots_require_explicit_selection')
    return {'status': status, 'source_file_counts': counts, 'projects': projects,
            'files_total': len(files), 'files_ignored_for_discovery': len(files) - len(active),
            'source_identity_sha256': digest({p: hashlib.sha256(v).hexdigest() for p, v in files.items()}),
            'ready_for_execution': False, 'behavior_verified': False, 'blockers': blockers}


def discover_pair(baseline, candidate, baseline_sha256, candidate_sha256, baseline_root, candidate_root):
    base = collect_archive(baseline, baseline_sha256, baseline_root)
    changed = collect_archive(candidate, candidate_sha256, candidate_root)
    paths = sorted(set(base) | set(changed))
    changes = [{'path': p, 'kind': 'added' if p not in base else 'deleted' if p not in changed else 'modified',
                'baseline_sha256': hashlib.sha256(base[p]).hexdigest() if p in base else None,
                'candidate_sha256': hashlib.sha256(changed[p]).hexdigest() if p in changed else None}
               for p in paths if base.get(p) != changed.get(p)]
    return {'schema': 'wheel-project-discovery-v1', 'operation': 'static_discovery_only',
            'baseline_archive_sha256': baseline_sha256, 'candidate_archive_sha256': candidate_sha256,
            'baseline': inspect_files(base), 'candidate': inspect_files(changed), 'changes': changes,
            'project_code_executed': False, 'model_requests': 0,
            'generic_execution_supported': False, 'source_uploaded_to_model': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for side in ('baseline', 'candidate'):
        parser.add_argument('--' + side + '-archive', type=Path, required=True)
        parser.add_argument('--' + side + '-sha256', required=True)
        parser.add_argument('--' + side + '-root', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = discover_pair(args.baseline_archive.read_bytes(), args.candidate_archive.read_bytes(),
                           args.baseline_sha256, args.candidate_sha256, args.baseline_root, args.candidate_root)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'baseline': result['baseline']['status'], 'candidate': result['candidate']['status'],
                      'changed_paths': len(result['changes']), 'generic_execution_supported': False}))


if __name__ == '__main__':
    main()
