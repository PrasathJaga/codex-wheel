"""Read-only extractor for the reviewed Java record/Map.of and Python tool surface."""
import ast
import re
from wheel.experiment import JAVA

CONTROLLER = JAVA + '/src/main/java/dev/codexwheel/refunds/web/RefundController.java'
REQUEST = JAVA + '/src/main/java/dev/codexwheel/refunds/domain/RefundRequest.java'
EFFECT = JAVA + '/src/main/java/dev/codexwheel/refunds/domain/RefundEffect.java'
META = 'wheel/meta_agent.py'
INPUTS = (CONTROLLER, REQUEST, EFFECT, META)
TYPES = {'String': 'string', 'long': 'integer', 'Instant': 'string(date-time)'}

class UnsupportedSchema(ValueError):
    pass


def one(pattern, text):
    matches = re.findall(pattern, text, re.S)
    if len(matches) != 1:
        raise UnsupportedSchema('Ambiguous or unsupported declaration')
    return matches[0]


def record_fields(text, name, annotated=False):
    raw = one(r'public record ' + name + r'\s*\((.*?)\)\s*\{', text)
    pattern = (r'\s*@JsonProperty\("([A-Za-z_][A-Za-z_0-9]*)"\)\s+'
               r'(String|long)\s+([A-Za-z_][A-Za-z_0-9]*)\s*' if annotated else
               r'\s*(String|long|Instant)\s+([A-Za-z_][A-Za-z_0-9]*)\s*')
    fields = {}; accessors = {}
    for part in raw.split(','):
        match = re.fullmatch(pattern, part)
        if not match:
            raise UnsupportedSchema('Unsupported record component')
        if annotated:
            public, kind, accessor = match.groups()
        else:
            kind, accessor = match.groups(); public = accessor
        if public in fields or accessor in accessors:
            raise UnsupportedSchema('Duplicate record field')
        fields[public] = TYPES[kind]; accessors[accessor] = TYPES[kind]
    if not fields:
        raise UnsupportedSchema('Empty record')
    return fields, accessors


def extract(sources):
    controller = sources[CONTROLLER]
    route, header, header_type, response = one(
        r'@PostMapping\("([^"\n]+)"\)\s+public Map<String,Object> refund\('
        r'@RequestHeader\("([^"\n]+)"\)\s+(String) key,\s*'
        r'@RequestBody RefundPayload body\)\s*\{\s*'
        r'RefundEffect effect = service\.issueRefund\(key, new RefundRequest\('
        r'body\.orderId\(\),\s*body\.amountMinorUnits\(\),\s*body\.currency\(\),\s*'
        r'body\.refundScope\(\)\)\);\s*return Map\.of\((.*?)\);\s*\}', controller)
    payload, _ = record_fields(controller, 'RefundPayload', annotated=True)
    request, _ = record_fields(sources[REQUEST], 'RefundRequest')
    effect, accessors = record_fields(sources[EFFECT], 'RefundEffect')
    parts = [part.strip() for part in response.split(',')]
    if not parts or len(parts) % 2:
        raise UnsupportedSchema('Unsupported response map')
    fields = {}
    for key, value in zip(parts[::2], parts[1::2]):
        if not re.fullmatch(r'"[A-Za-z_][A-Za-z_0-9]*"', key) or key[1:-1] in fields:
            raise UnsupportedSchema('Unsupported response key')
        accessor = re.fullmatch(r'effect\.([A-Za-z_][A-Za-z_0-9]*)\(\)', value)
        if accessor and accessor[1] in accessors:
            spec = {'type': accessors[accessor[1]]}
        elif re.fullmatch(r'"[A-Za-z_][A-Za-z_0-9]*"', value):
            spec = {'type': 'string', 'const': value[1:-1]}
        else:
            raise UnsupportedSchema('Unsupported response value')
        fields[key[1:-1]] = spec
    tree = ast.parse(sources[META])
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'TOOL' for t in node.targets)]
    if len(assignments) != 1:
        raise UnsupportedSchema('Tool declaration unavailable')
    try:
        tool = ast.literal_eval(assignments[0].value)
    except (ValueError, TypeError):
        raise UnsupportedSchema('Tool must be a literal') from None
    if (not isinstance(tool, dict) or tool.get('type') != 'function' or
            not isinstance(tool.get('function'), dict) or
            not isinstance(tool['function'].get('name'), str) or
            not isinstance(tool['function'].get('parameters'), dict)):
        raise UnsupportedSchema('Unsupported tool schema')
    return {'http': {'method': 'POST', 'path': route,
                     'headers': {header: TYPES[header_type]}, 'request': payload, 'response': fields},
            'records': {'RefundRequest': request, 'RefundEffect': effect},
            'tool': {key: tool['function'][key] for key in ('name', 'parameters')}}


def compare(base, candidate):
    try:
        left, right = extract(base), extract(candidate)
        return {'status': 'schema_unchanged' if left == right else 'schema_changed',
                'base': left, 'candidate': right, 'business_safety_verdict': None}
    except (UnsupportedSchema, SyntaxError):
        return {'status': 'unsupported', 'business_safety_verdict': None}
