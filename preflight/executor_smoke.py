"""Trusted CI harness: authored offline Java/Python executor controls, not discovery evaluation."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile

from preflight.isolated_executor import run_pair
from preflight.petclinic_adapter import digest
from preflight.project_discovery import discover_pair


def pack(files):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for path, content in sorted(files.items()):
            raw = content.encode()
            item = tarfile.TarInfo('source/' + path)
            item.size = len(raw)
            archive.addfile(item, io.BytesIO(raw))
    return stream.getvalue()


def exercise(language, image, output, candidate_bad=False, baseline_bad=False):
    if language == 'python':
        files = {'pyproject.toml': '[project]\nname="executor-control"\nversion="0.0.0"',
                 'logic.py': 'def value(): return 4\n',
                 'test_control.py': '''import os, pathlib, unittest, socket
from logic import value
class Control(unittest.TestCase):
 def test_execution(self):
  self.assertEqual(value(),4)
  self.assertFalse(pathlib.Path('state-marker').exists())
  pathlib.Path('state-marker').write_text('fresh world')
  self.assertNotIn('MODEL_API_KEY',os.environ)
  self.assertNotIn('GITHUB_TOKEN',os.environ)
  self.assertFalse(pathlib.Path('/var/run/docker.sock').exists())
  self.assertFalse(pathlib.Path('/work/preflight').exists())
  with socket.socket() as sock:
   sock.settimeout(0.3)
   self.assertNotEqual(sock.connect_ex(('1.1.1.1',80)),0)
'''}
        argv = ['python', '-m', 'unittest', 'discover', '-v']
    else:
        files = {'pom.xml': '<project><modelVersion>4.0.0</modelVersion><groupId>control</groupId><artifactId>control</artifactId><version>0</version></project>',
                 'Control.java': '''import java.nio.file.*;
class Control {
 public static void main(String[] args) throws Exception {
  if (3+4 != 7) throw new AssertionError("arithmetic");
  if (Files.exists(Path.of("state-marker"))) throw new AssertionError("reused state");
  Files.writeString(Path.of("state-marker"),"fresh world");
  if (System.getenv("MODEL_API_KEY") != null || System.getenv("GITHUB_TOKEN") != null) throw new AssertionError("credential");
  if (Files.exists(Path.of("/var/run/docker.sock")) || Files.exists(Path.of("/work/preflight"))) throw new AssertionError("private mount");
  System.out.println("Java executor control passed");
 }
}'''}
        argv = ['java', 'Control.java']
    bad = dict(files)
    if language == 'python':
        bad['logic.py'] = 'def value(): return 5\n'
    else:
        bad['Control.java'] = bad['Control.java'].replace('3+4 != 7', '3+4 != 8')
    baseline, candidate = pack(bad if baseline_bad else files), pack(bad if candidate_bad else files)
    source = {'baseline_sha256': hashlib.sha256(baseline).hexdigest(), 'candidate_sha256': hashlib.sha256(candidate).hexdigest(),
              'baseline_root': 'source', 'candidate_root': 'source'}
    discovery = discover_pair(baseline, candidate, source['baseline_sha256'], source['candidate_sha256'], 'source', 'source')
    manifest = {'schema': 'wheel-execution-manifest-v1', 'discovery_sha256': digest(discovery),
                'projects': [{'id': 'control', 'root': '.', 'language': language, 'image': image,
                              'build': [], 'test': [{'argv': argv, 'timeout_seconds': 120}], 'service': None}],
                'dependencies': [], 'observers': [], 'limits': {'cpu_millis': 1000, 'memory_mb': 512, 'pids': 128, 'world_timeout_seconds': 180},
                'network': {'build': 'reviewed_dependency_fetch_only', 'runtime': 'internal_only'}, 'reset': 'fresh_environment_per_world'}
    policy = {'schema': 'wheel-local-execution-policy-v1', 'manifest_sha256': digest(manifest), 'allowed_images': [image],
              'max_repetitions': 2, 'total_timeout_seconds': 600}
    output = Path(output)
    report = run_pair(baseline, candidate, source, manifest, policy, output, repetitions=1 if candidate_bad or baseline_bad else 2)
    for name, value in [('source', source), ('manifest', manifest), ('policy', policy), ('discovery', discovery)]:
        (output / (name + '.json')).write_text(json.dumps(value, indent=2) + '\n')
    expected = 'baseline_invalid' if baseline_bad else 'candidate_checks_failed' if candidate_bad else 'build_and_tests_passed'
    assert report['status'] == expected, (report['status'], report.get('error'))
    assert not report['cleanup_errors']
    assert len({w['volume'] for w in report['worlds']}) == len(report['worlds'])
    if baseline_bad:
        assert all(w['side'] == 'baseline' for w in report['worlds'])
    return {'language': language, 'expected': expected, 'observed': report['status'], 'worlds': len(report['worlds'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python-image', required=True)
    parser.add_argument('--java-image', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    results = []
    for language, image in [('python', args.python_image), ('java', args.java_image)]:
        results.append(exercise(language, image, args.output / (language + '-healthy')))
        results.append(exercise(language, image, args.output / (language + '-candidate-failure'), candidate_bad=True))
    results.append(exercise('python', args.python_image, args.output / 'invalid-baseline', baseline_bad=True))
    (args.output / 'summary.json').write_text(json.dumps({'kind': 'authored_executor_controls', 'results': results,
                                                        'meta_calls': 0, 'business_behavior_verified': False}, indent=2) + '\n')
    print(json.dumps(results))


if __name__ == '__main__':
    main()
