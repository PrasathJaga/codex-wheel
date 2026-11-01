"""Fetch reviewed public artifact bytes without running pip, Maven or project code."""
import argparse
import hashlib
import http.client
import ipaddress
import json
import multiprocessing
from pathlib import Path
import re
import socket
import ssl
import tempfile
import time
from urllib.parse import urlsplit

from preflight.petclinic_adapter import AdmissionError, digest, exact
from preflight.petclinic_evaluation import strict_json
from preflight.petclinic_source_intake import normalized_archive

MAX_TOTAL = 32 * 1024 * 1024
ORIGINS = {'python_wheel': 'files.pythonhosted.org', 'maven_artifact': 'repo.maven.apache.org'}


def hash_value(value):
    if type(value) is not str or not re.fullmatch(r'[0-9a-f]{64}', value):
        raise AdmissionError('SHA256 commitment required')


def validate(lock, policy):
    exact(lock, {'schema', 'discovery_sha256', 'purpose', 'artifacts'})
    exact(policy, {'schema', 'lock_sha256', 'allowed_urls', 'total_timeout_seconds', 'artifact_timeout_seconds'})
    if lock['schema'] != 'wheel-dependency-lock-v1' or policy['schema'] != 'wheel-dependency-acquisition-policy-v1':
        raise AdmissionError('Unsupported acquisition version')
    hash_value(lock['discovery_sha256'])
    if policy['lock_sha256'] != digest(lock):
        raise AdmissionError('Dependency lock changed or not reviewed')
    if lock['purpose'] not in ('execution_dependencies', 'authored_acquisition_control'):
        raise AdmissionError('Declared purpose required')
    if type(lock['artifacts']) is not list or not 1 <= len(lock['artifacts']) <= 64:
        raise AdmissionError('Artifact budget exceeded')
    for name, maximum in [('total_timeout_seconds', 600), ('artifact_timeout_seconds', 120)]:
        if type(policy[name]) is not int or not 1 <= policy[name] <= maximum:
            raise AdmissionError('Acquisition deadline outside bounds')
    if type(policy['allowed_urls']) is not list or len(policy['allowed_urls']) > 64:
        raise AdmissionError('Exact trusted URL allowlist required')
    if any(type(u) is not str for u in policy['allowed_urls']) or len(set(policy['allowed_urls'])) != len(policy['allowed_urls']):
        raise AdmissionError('Duplicate or invalid trusted URL')
    paths, urls, total = set(), set(), 0
    for artifact in lock['artifacts']:
        exact(artifact, {'kind', 'url', 'sha256', 'size_bytes', 'destination'})
        if type(artifact['kind']) is not str or artifact['kind'] not in ORIGINS:
            raise AdmissionError('Only wheels and Maven artifact files supported')
        hash_value(artifact['sha256'])
        size = artifact['size_bytes']
        if type(size) is not int or not 1 <= size <= 8 * 1024 * 1024:
            raise AdmissionError('Artifact size outside bounds')
        total += size
        url, destination = artifact['url'], artifact['destination']
        if type(url) is not str or len(url) > 2048 or any(ord(c) < 33 or ord(c) == 127 for c in url):
            raise AdmissionError('Invalid artifact URL')
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.netloc != ORIGINS[artifact['kind']]
                or parsed.query or parsed.fragment or '%' in parsed.path or '\\' in parsed.path
                or any(p in ('.', '..', '') for p in parsed.path.lstrip('/').split('/'))):
            raise AdmissionError('Unsupported public artifact URL')
        if url not in policy['allowed_urls']:
            raise AdmissionError('Artifact URL outside reviewed policy')
        if type(destination) is not str or len(destination) > 240 or '\\' in destination:
            raise AdmissionError('Invalid bundle destination')
        if any(p in ('', '.', '..') for p in destination.split('/')) or destination.startswith('/'):
            raise AdmissionError('Bundle path traversal')
        if artifact['kind'] == 'python_wheel':
            filename = parsed.path.rsplit('/', 1)[-1]
            if not re.fullmatch(r'[A-Za-z0-9_.+!-]+\.whl', filename) or destination != 'python/wheels/' + filename:
                raise AdmissionError('Wheel filename/destination mismatch')
        else:
            if not parsed.path.startswith('/maven2/') or not parsed.path.endswith(('.jar', '.pom')):
                raise AdmissionError('Maven artifact path required')
            if destination != 'maven/repository/' + parsed.path[len('/maven2/'):]:
                raise AdmissionError('Maven layout/destination mismatch')
        if destination in paths or url in urls:
            raise AdmissionError('Duplicate artifact path or URL')
        paths.add(destination)
        urls.add(url)
    if total > MAX_TOTAL:
        raise AdmissionError('Total artifact size exceeds budget')
    return lock


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        # Resolve once, reject private/mixed answers, connect to that exact address,
        # and still validate the public hostname via TLS/SNI. No proxy or redirect.
        addresses = sorted({item[4][0] for item in socket.getaddrinfo(self.host, 443, type=socket.SOCK_STREAM)})
        if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
            raise AdmissionError('Artifact origin did not resolve exclusively to public addresses')
        raw = socket.create_connection((addresses[0], 443), self.timeout)
        try:
            self.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


def _download_worker(sender, url, size, timeout, destination):
    connection = None
    try:
        parsed = urlsplit(url)
        connection = PinnedHTTPSConnection(parsed.hostname, timeout=timeout)
        connection.request('GET', parsed.path, headers={'User-Agent': 'codex-wheel-artifact-fetch-v1', 'Accept-Encoding': 'identity'})
        response = connection.getresponse()
        if response.status != 200:
            raise AdmissionError('Artifact HTTP status ' + str(response.status))
        length = response.getheader('Content-Length')
        if length is not None and (not length.isdigit() or int(length) != size):
            raise AdmissionError('Artifact Content-Length mismatch')
        count = 0
        with open(destination, 'wb') as stream:
            while True:
                block = response.read(min(65536, size + 1 - count))
                if not block:
                    break
                count += len(block)
                if count > size:
                    raise AdmissionError('Artifact exceeds declared size')
                stream.write(block)
        if count != size:
            raise AdmissionError('Truncated artifact')
        sender.send({'status': 'downloaded'})
    except Exception as error:
        sender.send({'status': 'failed', 'error_type': type(error).__name__, 'reason': str(error)[:300]})
    finally:
        if connection is not None:
            connection.close()
        sender.close()


def fetch(url, size, timeout):
    with tempfile.TemporaryDirectory(prefix='wheel-dependency-bytes-') as temporary:
        destination = str(Path(temporary) / 'artifact')
        context = multiprocessing.get_context('spawn')
        receiver, sender = context.Pipe(duplex=False)
        worker = context.Process(target=_download_worker, args=(sender, url, size, timeout, destination), daemon=True)
        worker.start()
        sender.close()
        try:
            if not receiver.poll(timeout):
                raise AdmissionError('Artifact hard deadline exceeded')
            try:
                receipt = receiver.recv()
            except EOFError as error:
                raise AdmissionError('Artifact worker exited without receipt') from error
            if receipt['status'] != 'downloaded':
                raise AdmissionError(receipt['reason'])
            return Path(destination).read_bytes()
        finally:
            receiver.close()
            if worker.is_alive():
                worker.terminate()
            worker.join(timeout=1)
            if worker.is_alive():
                worker.kill()
                worker.join(timeout=1)
            if worker.is_alive():
                raise AdmissionError('Artifact worker cleanup failed')


def acquire(lock, policy, output, *, fetcher=fetch):
    """Caller must keep policy outside project/model-controlled inputs.

    The fetcher override exists for trusted offline tests, never as a CLI plugin.
    """
    validate(lock, policy)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    report = {'schema': 'wheel-dependency-acquisition-result-v1', 'status': 'acquisition_failed',
              'lock_sha256': digest(lock), 'policy_sha256': digest(policy), 'discovery_sha256': lock['discovery_sha256'],
              'purpose': lock['purpose'], 'artifacts': [], 'bundle_sha256': None,
              'project_code_executed': False, 'packages_installed': False, 'model_requests': 0,
              'dependency_closure_verified': False}
    save = lambda: (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    deadline = time.monotonic() + policy['total_timeout_seconds']
    files = {}
    try:
        for artifact in lock['artifacts']:
            entry = {**artifact, 'status': 'attempted'}
            report['artifacts'].append(entry)
            save()
            timeout = min(policy['artifact_timeout_seconds'], deadline - time.monotonic())
            if timeout <= 0:
                raise AdmissionError('Total acquisition deadline exceeded')
            raw = fetcher(artifact['url'], artifact['size_bytes'], timeout)
            entry.update(observed_size_bytes=len(raw), observed_sha256=hashlib.sha256(raw).hexdigest())
            if len(raw) != artifact['size_bytes'] or entry['observed_sha256'] != artifact['sha256']:
                raise AdmissionError('Downloaded artifact size/hash mismatch')
            files[artifact['destination']] = raw
            entry['status'] = 'verified'
            save()
        bundle = normalized_archive(files)
        if len(bundle) > MAX_TOTAL:
            raise AdmissionError('Compressed dependency bundle exceeds budget')
        (output / 'dependencies.tar.gz').write_bytes(bundle)
        report.update(status='artifacts_verified', bundle_sha256=hashlib.sha256(bundle).hexdigest())
    except Exception as error:
        if report['artifacts'] and report['artifacts'][-1]['status'] == 'attempted':
            report['artifacts'][-1]['status'] = 'failed'
        report.update(error_type=type(error).__name__, error=str(error)[:300])
    finally:
        save()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lock', type=Path, required=True)
    parser.add_argument('--policy', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    def read(path):
        with path.open('rb') as stream:
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise AdmissionError('Acquisition configuration exceeds size budget')
        return strict_json(raw.decode())
    result = acquire(read(args.lock), read(args.policy), args.output)
    print(json.dumps({'status': result['status'], 'artifacts_attempted': len(result['artifacts']), 'packages_installed': False}))
    if result['status'] != 'artifacts_verified':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
