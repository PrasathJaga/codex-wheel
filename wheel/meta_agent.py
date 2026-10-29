"""Trusted, bounded Meta gateway. Model text never decides ledger correctness."""
import copy
import hashlib
import json
import os

MODEL = 'muse-spark-1.3'
TOOL = {'type': 'function', 'function': {'name': 'issue_refund',
    'description': 'Issue the authorized full-order synthetic refund exactly once.',
    'parameters': {'type': 'object', 'properties': {
        'order_id': {'type': 'string'}, 'amount_minor_units': {'type': 'integer'},
        'currency': {'type': 'string', 'enum': ['USD']},
        'refund_scope': {'type': 'string', 'enum': ['full_order']}},
        'required': ['order_id', 'amount_minor_units', 'currency', 'refund_scope'],
        'additionalProperties': False}}}

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()

def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def validate_intent(message, authorization):
    calls = message.get('tool_calls') or []
    if message.get('role') != 'assistant' or len(calls) != 1:
        raise ValueError('Exactly one assistant tool call required')
    call = calls[0]
    if call.get('type') != 'function' or not isinstance(call.get('id'), str) or not call['id']:
        raise ValueError('Invalid tool call identity')
    fn = call.get('function', {})
    if fn.get('name') != 'issue_refund':
        raise ValueError('Unexpected tool')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise ValueError('Duplicate argument')
            result[key] = value
        return result
    args = json.loads(fn['arguments'], object_pairs_hook=unique)
    expected = {**authorization, 'currency': 'USD', 'refund_scope': 'full_order'}
    if not isinstance(args, dict) or args != expected or type(args.get('amount_minor_units')) is not int:
        raise ValueError('Tool intent does not match independent authorization')
    return args

class MetaAgent:
    def __init__(self, client=None):
        self.calls = 0
        self.traces = []
        self.frozen = {}
        self.trace_path = None
        if client is None:
            # Remove before any build / Java / wrapper subprocess starts.
            key = os.environ.pop('MODEL_API_KEY', '')
            if not key: raise RuntimeError('MODEL_API_KEY is missing')
            from openai import OpenAI
            client = OpenAI(base_url='https://api.meta.ai/v1', api_key=key,
                            max_retries=0, timeout=60)
        self.client = client

    def generate(self, messages, initial):
        if self.calls >= 6: raise RuntimeError('Six-call budget exhausted')
        self.calls += 1
        try:
            response = self.client.chat.completions.create(model=MODEL,
                messages=messages, tools=[TOOL], tool_choice='auto' if initial else 'none',
                max_completion_tokens=1024, reasoning_effort='minimal')
        except Exception as error:
            # Never persist exception bodies, headers, request objects, or credentials.
            status = getattr(error, 'status_code', None)
            raise RuntimeError('Meta request failed; HTTP status ' + str(status)) from None
        if len(response.choices) != 1: raise ValueError('Expected one completion')
        choice = response.choices[0]
        message = choice.message.model_dump(exclude_none=True)
        self.traces.append({'ordinal': self.calls, 'response_id': response.id,
            'request_id': getattr(response, '_request_id', None), 'model': response.model,
            'usage': response.usage.model_dump() if response.usage else None,
            'finish_reason': choice.finish_reason, 'messages': copy.deepcopy(messages),
            'assistant': message})
        if self.trace_path:
            self.trace_path.write_text(json.dumps(self.traces, indent=2))
        if choice.finish_reason not in ('stop', 'tool_calls'):
            raise ValueError('Incomplete model completion')
        return message

    def prepare(self):
        for case, amount in [('M1', 2500), ('M2', 7500)]:
            authorization = {'order_id': 'ORD-SYN-TRIAL', 'amount_minor_units': amount}
            messages = [{'role': 'developer', 'content':
                'You are a support agent in a synthetic refund test. The order is eligible. '
                'Use issue_refund exactly once with the customer-authorized amount, USD, '
                'and full_order scope. After the tool result, give a brief customer response '
                'based only on that result. Do not invent ledger observations.'},
                {'role': 'user', 'content': f'Please refund my entire order ORD-SYN-TRIAL for USD {amount / 100:.2f}.'}]
            assistant = self.generate(messages, True)
            args = validate_intent(assistant, authorization)
            # Schema/authorization preflight only; no refund or mocked model response.
            frozen = {'messages': messages + [assistant], 'arguments': args,
                      'authorization': authorization, 'tool_call_id': assistant['tool_calls'][0]['id']}
            self.frozen[case] = {'payload': frozen, 'sha256': fingerprint(frozen)}
        return copy.deepcopy(self.frozen)

    def intent(self, case):
        frozen = self.frozen[case]
        if fingerprint(frozen['payload']) != frozen['sha256']:
            raise ValueError('Frozen conversation changed')
        return copy.deepcopy(frozen['payload'])

    def continue_world(self, case, receipt):
        frozen = self.intent(case)
        messages = frozen['messages'] + [{'role': 'tool',
            'tool_call_id': frozen['tool_call_id'], 'content': json.dumps(receipt)}]
        message = self.generate(messages, False)
        if message.get('tool_calls') or not isinstance(message.get('content'), str) or not message['content'].strip():
            raise ValueError('Expected final text without additional tools')
        return message
