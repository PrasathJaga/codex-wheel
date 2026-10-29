"""Constrained Docker execution with a narrow Unix-socket HTTP broker.

Trusted parent owns Meta, oracle, plan, evidence and Docker. Containers never
receive a Docker socket, host HOME, model key, oracle fixture or source tree.
The synthetic producer necessarily owns its evaluator token and writable ledger;
this is not an independent database or a hostile-kernel security proof.
"""
import http.client
from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import secrets
import socket
import socketserver
import subprocess
import threading
import time
import httpx

from wheel.experiment import child_env


def docker(*args, timeout=120, **kwargs):
    return subprocess.run(['docker', *map(str, args)], check=True, text=True,
                          capture_output=True, timeout=timeout, env=child_env(), **kwargs)


class UnixBroker:
    """Only POST /refunds; no arbitrary destination, evaluator route or headers."""
    def __init__(self, path, gateway_port):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                if self.path != '/refunds' or self.headers.get('Host') != 'gateway':
                    self.send_error(403); return
                try: length = int(self.headers.get('Content-Length', '0'))
                except ValueError:
                    self.send_error(400); return
                if not 0 < length <= 8192 or self.headers.get('Transfer-Encoding'):
                    self.send_error(413); return
                connection = http.client.HTTPConnection('127.0.0.1', gateway_port, timeout=8)
                try:
                    connection.request('POST', '/refunds', self.rfile.read(length), {
                        'Content-Type': 'application/json',
                        'Idempotency-Key': self.headers.get('Idempotency-Key', '')})
                    response = connection.getresponse()
                    body = response.read(8193)
                    if len(body) > 8192: raise ValueError('Response exceeds broker bound')
                    self.send_response(response.status)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers(); self.wfile.write(body)
                except (http.client.RemoteDisconnected, ConnectionError):
                    # Preserve the ambiguous downstream transport failure; never synthesize success.
                    self.close_connection = True
                    self.connection.shutdown(socket.SHUT_RDWR)
                finally: connection.close()
        class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
            daemon_threads = True
        self.server = Server(str(path), Handler)
        os.chmod(path, 0o600)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start(); return self

    def __exit__(self, *args):
        self.server.shutdown(); self.server.server_close(); self.thread.join()


class DockerRuntime:
    def __init__(self, root, scratch):
        self.root, self.scratch = Path(root), Path(scratch)
        self.uid = str(os.getuid()) + ':' + str(os.getgid())
        self.network = 'wheel-g6-' + secrets.token_hex(8)
        self.names = set()
        self.images = {}

    def prepare(self):
        docker('info')  # Fail before any paid call if Docker is unavailable.
        docker('pull', 'eclipse-temurin:21-jre', timeout=300)
        build = self.scratch / 'python-image'; build.mkdir()
        (build / 'Dockerfile').write_text(
            'FROM python:3.13-slim\nRUN pip install --no-cache-dir httpx==0.28.1\n')
        tag = self.network + '-python'
        docker('build', '-t', tag, build, timeout=300)
        for name, ref in [('java', 'eclipse-temurin:21-jre'), ('python', tag)]:
            self.images[name] = json.loads(docker('image', 'inspect', ref).stdout)[0]['Id']
        docker('network', 'create', '--internal', self.network)
        return dict(self.images)

    def limits(self):
        return ['--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                '--pids-limit=128', '--memory=512m', '--cpus=1', '--user', self.uid,
                '--tmpfs', '/tmp:rw,noexec,nosuid,size=96m', '--workdir', '/tmp']

    def probe(self):
        sentinel = self.scratch / 'host-only-oracle-sentinel'
        sentinel.write_text('synthetic probe; must remain outside container')
        script = """
import json, os, pathlib, socket
status = pathlib.Path('/proc/self/status').read_text()
checks = {'non_root': os.geteuid() != 0,
          'no_model_key': 'MODEL_API_KEY' not in os.environ,
          'no_evaluator_token': 'WHEEL_EVALUATOR_TOKEN' not in os.environ,
          'no_docker_socket': not pathlib.Path('/var/run/docker.sock').exists(),
          'no_host_fixture': not pathlib.Path(SENTINEL).exists(),
          'no_capabilities': 'CapEff:\t0000000000000000' in status,
          'no_new_privileges': 'NoNewPrivs:\t1' in status}
try:
    pathlib.Path('/root-write-probe').write_text('forbidden')
    checks['root_read_only'] = False
except OSError:
    checks['root_read_only'] = True
sock = socket.socket(); sock.settimeout(.5)
try:
    sock.connect(('1.1.1.1', 443)); checks['external_network_denied'] = False
except OSError:
    checks['external_network_denied'] = True
finally: sock.close()
print(json.dumps(checks))
""".replace('SENTINEL', repr(str(sentinel)))
        result = docker('run', '--rm', *self.limits(), '--network', 'none',
                        self.images['python'], 'python', '-B', '-c', script)
        checks = json.loads(result.stdout)
        network = json.loads(docker('network', 'inspect', self.network).stdout)[0]
        checks['producer_network_internal'] = network['Internal'] is True
        if not all(checks.values()):
            raise RuntimeError('Container confinement probe failed')
        return checks

    def start_java(self, jar, ledger_directory, token, log):
        name = self.network + '-' + secrets.token_hex(6)
        self.names.add(name)
        # Token stays out of argv; only this synthetic producer receives it.
        env = {**child_env(), 'WHEEL_EVALUATOR_TOKEN': token}
        subprocess.run(['docker', 'run', '-d', '--name', name, *self.limits(),
            '--network', self.network, '-p', '127.0.0.1::8080',
            '--mount', f'type=bind,src={jar},dst=/app.jar,readonly',
            '--mount', f'type=bind,src={ledger_directory},dst=/state',
            '-e', 'WHEEL_EVALUATOR_TOKEN', '-e', 'WHEEL_LEDGER_PATH=/state/ledger.tsv',
            self.images['java'], 'java', '-XX:ActiveProcessorCount=1', '-jar', '/app.jar',
            '--server.address=0.0.0.0'], env=env, check=True, text=True,
            capture_output=True, timeout=30)
        data = json.loads(docker('inspect', name).stdout)[0]
        config = data['HostConfig']
        if (data['Image'] != self.images['java'] or not config['ReadonlyRootfs'] or
                config['NetworkMode'] != self.network or config['Privileged'] or
                data['Config']['User'] != self.uid or
                'no-new-privileges' not in config['SecurityOpt'] or
                'ALL' not in config['CapDrop']):
            raise RuntimeError('Producer container configuration drift')
        p = int(data['NetworkSettings']['Ports']['8080/tcp'][0]['HostPort'])
        try:
            for _ in range(150):
                try:
                    if httpx.get(f'http://127.0.0.1:{p}/health', timeout=.5, trust_env=False).status_code == 200:
                        return name, p
                except httpx.TransportError: pass
                time.sleep(.2)
            raise RuntimeError('Container readiness timeout')
        except BaseException:
            self.stop_java(name, log); raise

    def stop_java(self, name, log):
        try:
            docker('stop', '-t', '10', name, timeout=25)
            log.write(docker('logs', name).stdout)
        finally:
            docker('rm', '-f', name)
            self.names.discard(name)

    def wrapper(self, source, bridge, arguments):
        # Only a copied candidate, trusted worker, and broker socket are mounted.
        name = self.network + '-wrapper-' + secrets.token_hex(6)
        self.names.add(name)
        try:
            result = docker('run', '--rm', '-i', '--name', name, *self.limits(),
                '--network', 'none',
                '--mount', f'type=bind,src={source},dst=/client.py,readonly',
                '--mount', f'type=bind,src={self.root / "wheel/wrapper_worker.py"},dst=/worker.py,readonly',
                '--mount', f'type=bind,src={bridge},dst=/bridge,readonly',
                self.images['python'], 'python', '-B', '/worker.py', '/client.py',
                'http://gateway', '/bridge/gateway.sock',
                input=json.dumps(arguments), timeout=45)
            return json.loads(result.stdout)
        finally:
            docker('rm', '-f', name) if name in self.names and self.exists(name) else None
            self.names.discard(name)

    def exists(self, name):
        return subprocess.run(['docker', 'inspect', name], env=child_env(),
                              capture_output=True, timeout=10).returncode == 0

    def close(self):
        for name in list(self.names): docker('rm', '-f', name)
        subprocess.run(['docker', 'network', 'rm', self.network], capture_output=True,
                       env=child_env(), timeout=30)
        subprocess.run(['docker', 'image', 'rm', self.network + '-python'], capture_output=True,
                       env=child_env(), timeout=30)
