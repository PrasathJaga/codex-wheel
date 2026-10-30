"""Request-level policy and accounting around the unchanged Meta integrations."""
import copy
import json
import time
from types import SimpleNamespace
from wheel.meta_agent import MODEL

class RequestLimit(RuntimeError):
    pass


class RequestLedger:
    LIMITS = {('C2', 'support'): 42, ('C4', 'support'): 20, ('C4', 'investigator'): 24}

    def __init__(self, client, path):
        self.client = client
        self.path = path
        self.attempts = []
        self.phase = 'selection'

    def persist(self):
        self.path.write_text(json.dumps(self.attempts, indent=2, sort_keys=True))

    def scoped(self, method, role, selection):
        if (method, role) not in self.LIMITS:
            raise ValueError('Unsupported request scope')
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
            create=lambda **kwargs: self.create(method, role, selection, **kwargs))))

    def create(self, method, role, selection, **kwargs):
        limit = self.LIMITS[(method, role)]
        if sum(a['method'] == method and a['role'] == role for a in self.attempts) >= limit:
            raise RequestLimit('Method request budget exhausted')
        initial = self.phase == 'selection'
        if role == 'investigator' and not initial:
            raise RequestLimit('Investigation after world freeze is forbidden')
        scoped = [a for a in self.attempts if a['selection'] == selection and a['role'] == role]
        if (role == 'investigator' and len(scoped) >= 6) or (role == 'support' and initial and scoped):
            raise RequestLimit('Selection cannot be retried')
        expected_tokens, effort = (2048, 'low') if role == 'investigator' else (1024, 'minimal')
        if (kwargs.get('model') != MODEL or kwargs.get('max_completion_tokens') != expected_tokens or
                kwargs.get('reasoning_effort') != effort or kwargs.get('tool_choice') != 'auto'):
            raise RequestLimit('Request configuration differs from frozen policy')
        if len(json.dumps(kwargs['messages'], ensure_ascii=False)) > 100000:
            raise RequestLimit('Message character budget exceeded')
        item = {'ordinal': len(self.attempts) + 1, 'method': method, 'role': role,
                'selection': selection, 'phase': self.phase, 'status': 'attempted',
                'request': copy.deepcopy(kwargs), 'response_id': None, 'usage': None}
        self.attempts.append(item); self.persist()
        started = time.monotonic()
        try:
            response = self.client.chat.completions.create(**kwargs)
            item.update(status='response_received', response_id=response.id, model=response.model,
                        request_id=getattr(response, '_request_id', None),
                        usage=response.usage.model_dump() if response.usage else None,
                        response=response.model_dump(exclude_none=True))
            if response.model != MODEL:
                raise RequestLimit('Unexpected response model')
            return response
        except Exception as error:
            item.update(status='request_error', error_type=type(error).__name__,
                        http_status=getattr(error, 'status_code', None))
            raise
        finally:
            item['runtime_seconds'] = time.monotonic() - started
            self.persist()
