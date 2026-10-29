"""Credential-free wrapper subprocess; reads a frozen intent, returns its receipt."""
import importlib.util
import json
import sys
import httpx

module_path, url = sys.argv[1:3]
uds = sys.argv[3] if len(sys.argv) == 4 else None
spec = importlib.util.spec_from_file_location('trial_client', module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
errors = []
class ObservedClient(httpx.Client):
    def send(self, *args, **kwargs):
        try: return super().send(*args, **kwargs)
        except httpx.TransportError as error:
            errors.append(type(error).__name__)
            raise
transport = httpx.HTTPTransport(uds=uds) if uds else None
with ObservedClient(base_url=url, trust_env=False, timeout=3, transport=transport) as client:
    receipt = module.RefundTool(client=client).issue_refund(**json.load(sys.stdin))
print(json.dumps({'receipt': receipt, 'transport_errors': errors}))
