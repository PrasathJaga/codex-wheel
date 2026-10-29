"""Bounded loopback fault gateway for synthetic fixtures; no evaluator credentials."""
import hashlib
import http.client
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ACTIONS = {'PASS_THROUGH', 'DROP_DOWNSTREAM_BEFORE_RESPONSE', 'REPLACE_DOWNSTREAM_STATUS_502'}

class Gateway:
    def __init__(self, upstream_port, rule):
        if set(rule) != {'action', 'min', 'max'} or rule['action'] not in ACTIONS:
            raise ValueError('Invalid fault rule')
        if type(rule['min']) is not int or type(rule['max']) is not int or not 1 <= rule['min'] <= rule['max'] <= 100000000:
            raise ValueError('Invalid bounds')
        self.events = []
        self.applied = 0
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                if self.path != '/refunds':
                    self.send_error(403); return
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 8192:
                    self.send_error(413); return
                body = self.rfile.read(length)
                payload = json.loads(body)
                key = self.headers.get('Idempotency-Key', '')
                connection = http.client.HTTPConnection('127.0.0.1', upstream_port, timeout=3)
                try:
                    connection.request('POST', '/refunds', body, {'Content-Type':'application/json', 'Idempotency-Key':key})
                    response = connection.getresponse()
                    buffered = response.read(8193)
                    if len(buffered) > 8192: raise ValueError('Upstream body exceeds bound')
                    action = 'PASS_THROUGH'
                    if response.status == 200 and owner.applied == 0 and rule['min'] <= payload['amount_minor_units'] <= rule['max']:
                        action = rule['action']
                        if action != 'PASS_THROUGH': owner.applied += 1
                    owner.events.append({'upstream_status':response.status, 'action':action,
                        'key_sha256':hashlib.sha256(key.encode()).hexdigest(),
                        'upstream_body':json.loads(buffered)})
                    if action == 'DROP_DOWNSTREAM_BEFORE_RESPONSE':
                        self.close_connection = True
                        self.connection.shutdown(socket.SHUT_RDWR)
                        self.connection.close(); return
                    status = 502 if action == 'REPLACE_DOWNSTREAM_STATUS_502' else response.status
                    self.send_response(status)
                    self.send_header('Content-Type','application/json')
                    self.send_header('Content-Length',str(len(buffered)))
                    self.end_headers(); self.wfile.write(buffered)
                finally: connection.close()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
    def __enter__(self): self.thread.start(); return self
    def __exit__(self, *args): self.server.shutdown(); self.server.server_close(); self.thread.join()
