"""Pinned commit intake for the reviewed synthetic refund fixture only.

A commit hash is provenance, not permission to execute arbitrary source. Only
source bytes already reviewed in the trusted runner's four fixture variants are
admitted. Builds use the trusted project template, never repository scripts.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from wheel.experiment import ROOT, JAVA, DOMAIN, CLIENT, digest, child_env
from wheel.g6 import variants
from wheel.plan_guard import IntegrityError

SHA = re.compile(r'[0-9a-f]{40}\Z')


def git(root, *args, input=None, env=None):
    return subprocess.run(['git', '-C', str(root), *args], input=input,
        capture_output=True, check=True, timeout=30,
        env={**child_env(), 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null', **(env or {})}).stdout


def commit(root, revision):
    if not isinstance(revision, str) or not SHA.fullmatch(revision):
        raise IntegrityError('A full lowercase 40-character commit SHA is required')
    if git(root, 'rev-parse', '--verify', revision + '^{commit}').decode().strip() != revision:
        raise IntegrityError('Revision is not the requested commit')
    return revision


def source(root, revision, path):
    tree = git(root, 'ls-tree', revision, '--', path).decode().strip()
    if not tree.startswith('100644 blob ') or tree.split('\t')[-1] != path:
        raise IntegrityError('Missing, executable or symbolic-link source is unsupported')
    ref = revision + ':' + path
    if int(git(root, 'cat-file', '-s', ref)) > 131072:
        raise IntegrityError('Source exceeds fixture bound')
    return git(root, 'show', ref).decode('utf-8')


def inspect(root, base, candidate, changed_side):
    root = Path(root)
    commit(root, base); commit(root, candidate)
    if changed_side not in ('java', 'python'):
        raise IntegrityError('Unsupported changed side')
    path = DOMAIN if changed_side == 'java' else CLIENT
    changes = git(root, 'diff', '--no-renames', '--name-only', base, candidate, '--').decode().splitlines()
    if changes != [path]:
        raise IntegrityError('Exactly one supported changed file and an unchanged peer are required')
    java, python = variants()  # Trusted checkout, not incoming repository instructions.
    reviewed = java if changed_side == 'java' else python
    base_java = source(root, base, DOMAIN); base_python = source(root, base, CLIENT)
    if base_java != java['base'] or base_python != python['base']:
        raise IntegrityError('Baseline differs from the reviewed fixture')
    changed = source(root, candidate, path)
    matches = [name for name, text in reviewed.items() if name != 'base' and changed == text]
    if len(matches) != 1:
        raise IntegrityError('Candidate source has not been reviewed by this fixture policy')
    case = matches[0]
    peer = CLIENT if changed_side == 'java' else DOMAIN
    if source(root, candidate, peer) != source(root, base, peer):
        raise IntegrityError('Unchanged peer drift')
    # Reject altered/extra producer build inputs, even if the source entry matches.
    trusted = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / JAVA / 'src').rglob('*') if p.is_file())
    trusted += [JAVA + '/pom.xml', 'services/support-agent-python/pyproject.toml']
    expected_java = sorted(p for p in trusted if p.startswith(JAVA + '/'))
    incoming_java = sorted(git(root, 'ls-tree', '-r', '--name-only', base, '--', JAVA + '/src', JAVA + '/pom.xml').decode().splitlines())
    if incoming_java != expected_java:
        raise IntegrityError('Unsupported producer source inventory')
    for name in trusted:
        if name != DOMAIN and source(root, base, name).encode() != (ROOT / name).read_bytes():
            raise IntegrityError('Unreviewed build or producer input: ' + name)
    return {'schema': 'reviewed-refund-intake-v1', 'case': case,
            'base_commit': base, 'candidate_commit': candidate,
            'fixed_peer_commit': base, 'changed_side': changed_side, 'changed_path': path,
            'java': {'base': base_java, 'candidate': source(root, candidate, DOMAIN)},
            'python': {'base': base_python, 'candidate': source(root, candidate, CLIENT)},
            'source_hashes': {'java': {'base': digest(base_java.encode()), 'candidate': digest(source(root, candidate, DOMAIN).encode())},
                              'python': {'base': digest(base_python.encode()), 'candidate': digest(source(root, candidate, CLIENT).encode())}},
            'admission': 'exact_reviewed_source_bytes',
            'limit': 'not_general_or_hostile_repository_support'}


def fixture_commit(root, base, path, text, case):
    """Create a real local synthetic commit without changing a branch/worktree."""
    commit(root, base)
    blob = git(root, 'hash-object', '-w', '--stdin', input=text.encode()).decode().strip()
    with tempfile.TemporaryDirectory(prefix='wheel-index-') as directory:
        env = {'GIT_INDEX_FILE': str(Path(directory) / 'index')}
        git(root, 'read-tree', base, env=env)
        git(root, 'update-index', '--add', '--cacheinfo', '100644', blob, path, env=env)
        tree = git(root, 'write-tree', env=env).decode().strip()
        identity = {'GIT_AUTHOR_NAME': 'Codex Wheel Synthetic Fixture',
                    'GIT_AUTHOR_EMAIL': 'fixture@codex-wheel.invalid',
                    'GIT_COMMITTER_NAME': 'Codex Wheel Synthetic Fixture',
                    'GIT_COMMITTER_EMAIL': 'fixture@codex-wheel.invalid',
                    'GIT_AUTHOR_DATE': '2026-10-30T00:00:00+00:00',
                    'GIT_COMMITTER_DATE': '2026-10-30T00:00:00+00:00'}
        return git(root, 'commit-tree', tree, '-p', base,
                   input=('Synthetic pinned replay fixture ' + case + '\n').encode(), env=identity).decode().strip()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--base', required=True); parser.add_argument('--candidate', required=True)
    parser.add_argument('--changed-side', required=True, choices=['java', 'python'])
    args = parser.parse_args()
    try: print(json.dumps(inspect(args.repo, args.base, args.candidate, args.changed_side), indent=2))
    except Exception as error:
        print(json.dumps({'status': 'unsupported', 'error_type': type(error).__name__}))
        raise SystemExit(1) from None
