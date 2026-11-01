"""Complete bounded HTTP tool contract, execution and independent expectation checks.

No model calls, arbitrary URLs, SQL, shell, credentials or domain-specific actions.
"""
import base64
import copy
import hashlib
import http.client
import json
import multiprocessing
import re
import time

from preflight.execution_manifest import identifier, integer, text
from preflight.isolated_executor import ExecutionError
from preflight.petclinic_adapter import AdmissionError, digest, exact
from preflight.petclinic_evaluation import strict_json


def schema_value(schema, value):
    kind = schema['type']
    if kind == 'string':
        if type(value) is not str or not schema['minLength'] <= len(value) <= schema['maxLength']:
            raise AdmissionError('String outside tool schema')
    elif kind == 'integer':
        integer(value, schema['minimum'], schema['maximum'])
    elif kind == 'boolean':
        if type(value) is not bool:
            raise AdmissionError('Boolean required')
    else:
        raise AdmissionError('Unsupported scalar type')


def validate_body_schema(value):
    if value is None:
        return
    exact(value, {'type', 'properties', 'required', 'additionalProperties'})
    if value['type'] != 'object' or value['additionalProperties'] is not False or type(value['properties']) is not dict or len(value['properties']) > 16:
        raise AdmissionError('Closed bounded object schema required')
    required = value['required']
    if type(required) is not list or any(type(k) is not str for k in required) or len(required) != len(set(required)) or not set(required) <= set(value['properties']):
        raise AdmissionError('Invalid required properties')
    for name, schema in value['properties'].items():
        identifier(name)
        if type(schema) is not dict:
            raise AdmissionError('Scalar schema object required')
        if schema.get('type') == 'string':
            exact(schema, {'type', 'minLength', 'maxLength'})
            integer(schema['minLength'], 0, 256)
            integer(schema['maxLength'], schema['minLength'], 256)
        elif schema.get('type') == 'integer':
            exact(schema, {'type', 'minimum', 'maximum'})
            integer(schema['minimum'], -1000000, 1000000)
            integer(schema['maximum'], schema['minimum'], 1000000)
        elif schema.get('type') == 'boolean':
            exact(schema, {'type'})
        else:
            raise AdmissionError('Unsupported request schema')


def validate_body(schema, value):
    if schema is None:
        if value is not None:
            raise AdmissionError('Operation has no body')
        return
    if type(value) is not dict or not set(schema['required']) <= set(value) or not set(value) <= set(schema['properties']):
        raise AdmissionError('Body properties differ from tool schema')
    for name, scalar in value.items():
        schema_value(schema['properties'][name], scalar)


def tool_schema(interface, contract):
    """Exact JSON schema delivered with approved source/interface/expectation inputs."""
    actions = []
    for operation in interface['operations']:
        actions.append({'type':'object','additionalProperties':False,'required':['operation','body'],
                        'properties':{'operation':{'const':operation['id']},
                                      'body': operation['body_schema'] or {'type':'null'}}})
    return {'type':'object','additionalProperties':False,
            'required':['schema','interface_sha256','contract_sha256','actions'],
            'properties':{'schema':{'const':'wheel-http-experiment-v1'},
                          'interface_sha256':{'const':digest(interface)}, 'contract_sha256':{'const':digest(contract)},
                          'actions':{'type':'array','minItems':1,'maxItems':8,'items':{'oneOf':actions}}}}


def admit_experiment(manifest, lifecycle_policy, sources, bundle):
    exact(bundle, {'interface', 'contract', 'plan', 'policy'})
    interface, contract, plan, policy = (bundle[k] for k in ('interface','contract','plan','policy'))
    exact(policy, {'schema','lifecycle_policy_sha256','interface_sha256','contract_sha256','plan_sha256'})
    if (policy['schema'] != 'wheel-http-experiment-policy-v1' or policy['lifecycle_policy_sha256'] != digest(lifecycle_policy)
            or any(policy[k+'_sha256'] != digest(bundle[k]) for k in ('interface','contract','plan'))):
        raise AdmissionError('Experiment differs from trusted frozen policy')
    exact(interface, {'schema','manifest_sha256','operations'})
    exact(contract, {'schema','manifest_sha256','provenance','checks'})
    if (interface['schema'] != 'wheel-http-interface-v1' or contract['schema'] != 'wheel-http-contract-v1'
            or interface['manifest_sha256'] != digest(manifest) or contract['manifest_sha256'] != digest(manifest)):
        raise AdmissionError('Interface/contract not bound to current manifest')
    exact(contract['provenance'], {'kind','reference'})
    if contract['provenance']['kind'] not in ('developer_declared','reviewed_existing_contract'):
        raise AdmissionError('Declared expectation source required')
    text(contract['provenance']['reference'], 1000)
    if type(interface['operations']) is not list or not 1 <= len(interface['operations']) <= 16:
        raise AdmissionError('Operation budget exceeded')
    operations = {}
    for operation in interface['operations']:
        exact(operation, {'id','method','path','body_schema','source_refs'})
        key = identifier(operation['id'])
        if key in operations or operation['method'] not in ('GET','POST','PUT','PATCH','DELETE'):
            raise AdmissionError('Duplicate or unsupported operation')
        route = operation['path']
        if type(route) is not str or not re.fullmatch(r'/[A-Za-z0-9_/-]{0,199}', route) or route.startswith('//') or any(v in ('.','..') for v in route.split('/')):
            raise AdmissionError('Fixed internal route required')
        validate_body_schema(operation['body_schema'])
        if operation['method'] == 'GET' and operation['body_schema'] is not None:
            raise AdmissionError('GET body unsupported')
        refs = operation['source_refs']
        if type(refs) is not list or not 2 <= len(refs) <= 6:
            raise AdmissionError('Source references from both revisions required')
        sides = set()
        for ref in refs:
            exact(ref, {'side','path','line_start','line_end'})
            side, path = ref['side'], ref['path']
            if type(side) is not str or side not in sources or type(path) is not str or path not in sources[side]:
                raise AdmissionError('Unknown source reference')
            integer(ref['line_start'], 1, 1000000)
            integer(ref['line_end'], ref['line_start'], ref['line_start'] + 7)
            try:
                lines = sources[side][path].decode('utf-8').splitlines()
            except UnicodeError as error:
                raise AdmissionError('Non-text source reference') from error
            if ref['line_end'] > len(lines):
                raise AdmissionError('Source reference out of range')
            sides.add(side)
        if sides != {'baseline','candidate'}:
            raise AdmissionError('Both source sides required')
        operations[key] = operation
    if type(contract['checks']) is not list or not 1 <= len(contract['checks']) <= 16:
        raise AdmissionError('Contract check budget exceeded')
    checks = {}
    for check in contract['checks']:
        exact(check, {'operation','statuses','json_equals'})
        key = identifier(check['operation'])
        if key not in operations or key in checks or type(check['statuses']) is not list or not 1 <= len(check['statuses']) <= 8:
            raise AdmissionError('Invalid operation expectation')
        for status in check['statuses']:
            integer(status, 100, 599)
        if type(check['json_equals']) is not list or len(check['json_equals']) > 8:
            raise AdmissionError('JSON expectation budget exceeded')
        for assertion in check['json_equals']:
            exact(assertion, {'path','value'})
            if type(assertion['path']) is not list or not 1 <= len(assertion['path']) <= 8:
                raise AdmissionError('Bounded JSON path required')
            for part in assertion['path']:
                if type(part) is str:
                    text(part, 64)
                elif type(part) is int:
                    integer(part, 0, 1000)
                else:
                    raise AdmissionError('Invalid JSON path component')
            if assertion['value'] is not None and type(assertion['value']) not in (str,int,bool):
                raise AdmissionError('Only scalar equality expectations supported')
            if len(json.dumps(assertion['value'])) > 512:
                raise AdmissionError('Expectation value too large')
        checks[key] = check
    exact(plan, {'schema','interface_sha256','contract_sha256','actions'})
    if (plan['schema'] != 'wheel-http-experiment-v1' or plan['interface_sha256'] != digest(interface)
            or plan['contract_sha256'] != digest(contract) or type(plan['actions']) is not list or not 1 <= len(plan['actions']) <= 8):
        raise AdmissionError('Unfrozen or unsupported experiment')
    for action in plan['actions']:
        exact(action, {'operation','body'})
        key = identifier(action['operation'])
        if key not in operations or key not in checks:
            raise AdmissionError('Unapproved action or missing expectation')
        validate_body(operations[key]['body_schema'], action['body'])
    return copy.deepcopy(bundle)


def _request_worker(sender, address, port, operation, body, timeout):
    connection = http.client.HTTPConnection(address, port, timeout=timeout)
    try:
        payload = None if body is None else json.dumps(body, separators=(',',':')).encode()
        connection.request(operation['method'], operation['path'], body=payload,
                           headers={'Connection':'close', **({'Content-Type':'application/json'} if payload is not None else {})})
        response = connection.getresponse()
        raw = response.read(65537)
        if len(raw) > 65536:
            sender.send({'error':'response_limit_exceeded'})
        else:
            sender.send({'status':response.status,'body_base64':base64.b64encode(raw).decode(),
                         'body_sha256':hashlib.sha256(raw).hexdigest(),'body_bytes':len(raw)})
    except Exception as error:
        sender.send({'error':type(error).__name__})
    finally:
        connection.close()
        sender.close()


def request(address, port, operation, body, timeout):
    context = multiprocessing.get_context('spawn')
    receiver, sender = context.Pipe(duplex=False)
    worker = context.Process(target=_request_worker,args=(sender,address,port,operation,body,timeout),daemon=True)
    worker.start()
    sender.close()
    try:
        if not receiver.poll(timeout):
            return {'error':'request_deadline_exceeded'}
        try:
            return receiver.recv()
        except EOFError:
            return {'error':'worker_without_evidence'}
    finally:
        receiver.close()
        if worker.is_alive(): worker.terminate()
        worker.join(timeout=1)
        if worker.is_alive(): worker.kill(); worker.join(timeout=1)
        if worker.is_alive(): raise ExecutionError('HTTP experiment worker cleanup failed')


def assess(response, check):
    if response['status'] not in check['statuses']:
        return ['unexpected_http_status']
    failures = []
    if check['json_equals']:
        try:
            value = strict_json(base64.b64decode(response['body_base64'], validate=True).decode('utf-8'))
        except (ValueError, UnicodeError):
            return ['expected_json_body_invalid']
        for index, assertion in enumerate(check['json_equals']):
            try:
                actual = value
                for part in assertion['path']:
                    if type(part) is str and type(actual) is dict: actual = actual[part]
                    elif type(part) is int and type(actual) is list: actual = actual[part]
                    else: raise KeyError('JSON shape')
                if type(actual) is not type(assertion['value']) or actual != assertion['value']:
                    failures.append('json_equality_' + str(index))
            except (KeyError, IndexError):
                failures.append('json_path_missing_' + str(index))
    return failures


def execute(bundle, address, port, timeout):
    deadline = time.monotonic() + timeout
    operations = {o['id']:o for o in bundle['interface']['operations']}
    checks = {c['operation']:c for c in bundle['contract']['checks']}
    result = {'status':'contract_satisfied','plan_sha256':digest(bundle['plan']),'events':[]}
    for action in bundle['plan']['actions']:
        left = deadline - time.monotonic()
        if left <= 0:
            result.update(status='execution_error', error='experiment_deadline_exceeded')
            break
        response = request(address,port,operations[action['operation']],action['body'],min(5,left))
        event = {'action':action,'response':response}
        result['events'].append(event)
        if 'error' in response:
            result.update(status='execution_error',error=response['error'])
            break
        event['failures'] = assess(response,checks[action['operation']])
        if event['failures']: result['status'] = 'contract_violated'
    result['evidence_sha256'] = digest(result)
    return result
