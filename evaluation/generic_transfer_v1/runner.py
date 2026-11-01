"""Frozen comparison of supplied source-aware conventional plan and Wheel Meta.

No case generation, provider client, paid workflow or outcome tuning lives here.
"""
import base64
import hashlib
import json
from pathlib import Path
import time

from preflight.generic_investigator import prepare, selection, implementation_sha256, run_investigation
from preflight.petclinic_adapter import AdmissionError, digest, exact
from preflight.service_executor import run_service_pair

ROOT=Path(__file__).resolve().parent
METHODS=('source_aware_conventional','wheel_meta')


def verify_protocol():
    protocol=json.loads((ROOT/'protocol.json').read_text())
    if digest(protocol)!=(ROOT/'protocol.sha256').read_text().strip():
        raise AdmissionError('Comparison protocol commitment changed')
    if protocol['implementation_sha256']!=implementation_sha256():
        raise AdmissionError('Frozen investigator implementation changed')
    if protocol['comparison_runner_sha256']!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        raise AdmissionError('Comparison implementation changed')
    return protocol


def validate_case(case):
    protocol=verify_protocol()
    exact(case,{'id','inputs','conventional','provenance','expectation_commitment_sha256'})
    from preflight.execution_manifest import identifier
    identifier(case['id'])
    commitment=case['expectation_commitment_sha256']
    if type(commitment) is not str or len(commitment)!=64 or any(c not in '0123456789abcdef' for c in commitment):
        raise AdmissionError('Sealed expectation commitment required')
    provenance=case['provenance']
    exact(provenance,{'kind','preparer','prepared_after_protocol','source_reference','effort_seconds'})
    if provenance['kind'] not in ('independent_authored','upstream_existing_change','internal_authored'):
        raise AdmissionError('Unrecognized case origin')
    if type(provenance['preparer']) is not str or not provenance['preparer'].strip():
        raise AdmissionError('Preparer declaration required')
    if provenance['prepared_after_protocol']!=digest(protocol):
        raise AdmissionError('Preparation must refer to frozen protocol')
    if type(provenance['source_reference']) is not str or not provenance['source_reference'].strip():
        raise AdmissionError('Source provenance evidence reference required')
    effort=provenance['effort_seconds']
    if effort is not None and (type(effort) is not int or effort<0):
        raise AdmissionError('Effort must be measured nonnegative seconds or unknown')
    inputs=case['inputs']
    exact(inputs,{'baseline_base64','candidate_base64','source','manifest','lifecycle','interface','contract','policy'})
    if any(type(inputs[k]) is not str or len(inputs[k])>45*1024*1024 for k in ('baseline_base64','candidate_base64')):
        raise AdmissionError('Encoded archive budget exceeded')
    try:
        baseline=base64.b64decode(inputs['baseline_base64'],validate=True)
        candidate=base64.b64decode(inputs['candidate_base64'],validate=True)
    except (ValueError,TypeError) as error:
        raise AdmissionError('Invalid encoded source archives') from error
    if len(baseline)>32*1024*1024 or len(candidate)>32*1024*1024:
        raise AdmissionError('Source archive budget exceeded')
    packet,sources=prepare(baseline,candidate,*[inputs[k] for k in ('source','manifest','lifecycle','interface','contract','policy')])
    if sources['baseline']==sources['candidate']:
        raise AdmissionError('Unchanged pair is a control, not a fresh change')
    if inputs['policy']['attempt_id']!=case['id']+'_wheel_meta':
        raise AdmissionError('Method claim identity mismatch')
    conventional=case['conventional']
    exact(conventional,{'context_sha256','proposal','preparation_kind','effort_seconds'})
    if conventional['context_sha256']!=digest(packet):
        raise AdmissionError('Conventional source context differs from Meta context')
    if conventional['preparation_kind'] not in ('human_source_aware','ai_assisted_source_aware','deterministic_source_aware'):
        raise AdmissionError('Conventional preparation must be disclosed')
    effort=conventional['effort_seconds']
    if effort is not None and (type(effort) is not int or effort<0):
        raise AdmissionError('Conventional preparation effort must be measured or unknown')
    if selection(conventional['proposal'],packet,inputs['manifest'],inputs['lifecycle'],sources,inputs['interface'],inputs['contract']) is None:
        raise AdmissionError('Conventional packet requires one predeclared valid experiment')
    return protocol,baseline,candidate,packet,sources


def register(case,registry):
    protocol,_,_,packet,_=validate_case(case)
    if registry['protocol_sha256']!=digest(protocol):raise AdmissionError('Registry protocol mismatch')
    if registry['attempts']:raise AdmissionError('Registration closed after first attempted execution')
    if len(registry['cases'])>=protocol['case_limit']:raise AdmissionError('Case limit reached')
    if any(r['id']==case['id'] or r['case_sha256']==digest(case) for r in registry['cases']):
        raise AdmissionError('Duplicate case')
    language=case['inputs']['manifest']['projects'][0]['language']
    if any(r['language']==language for r in registry['cases']):raise AdmissionError('One registered case per language')
    row={'id':case['id'],'language':language,'case_sha256':digest(case),'context_sha256':digest(packet),
         'origin':case['provenance']['kind'],'independence':'unverified_requires_external_review'}
    registry['cases'].append(row)
    return row


def validate_review(case,registry,review):
    exact(review,{'case_sha256','protocol_sha256','provenance_verified','reviewer','evidence_reference'})
    if not any(r['id']==case['id'] and r['case_sha256']==digest(case) for r in registry['cases']):
        raise AdmissionError('Case not registered')
    if review['case_sha256']!=digest(case) or review['protocol_sha256']!=registry['protocol_sha256'] or review['provenance_verified'] is not True:
        raise AdmissionError('External provenance review required before execution')
    if (type(review['reviewer']) is not str or not review['reviewer'].strip()
            or review['reviewer'].strip().casefold()==case['provenance']['preparer'].strip().casefold()
            or type(review['evidence_reference']) is not str or not review['evidence_reference'].strip()):
        raise AdmissionError('Separate reviewer and evidence required')
    if case['provenance']['kind']=='internal_authored':
        raise AdmissionError('Internal authored cases cannot qualify for this transfer evaluation')


def run_method(case,registry,review,method,output,claims,gateway_factory=None):
    protocol,baseline,candidate,packet,sources=validate_case(case)
    if registry['protocol_sha256']!=digest(protocol) or len(registry['cases'])>protocol['case_limit']:
        raise AdmissionError('Registry outside frozen protocol')
    if len(registry['attempts'])>=protocol['case_limit']*len(METHODS):
        raise AdmissionError('Comparison method budget exhausted')
    validate_review(case,registry,review)
    if len(registry['cases'])!=protocol['case_limit'] or {r['language'] for r in registry['cases']}!={'java','python'}:
        raise AdmissionError('Complete Java/Python case batch must be registered before first execution')
    if any(a.get('stop_required') or a['status'] not in ('confirmed_contract_violation','no_violation_observed','inconclusive') for a in registry['attempts']):
        raise AdmissionError('An unresolved or failed attempt stops further comparison')
    if method not in METHODS:raise AdmissionError('Unknown comparison method')
    if not any(r['id']==case['id'] for r in registry['cases']):raise AdmissionError('Case not registered')
    if any(a['case_id']==case['id'] and a['method']==method for a in registry['attempts']):
        raise AdmissionError('Method already attempted; no resampling')
    claims=Path(claims)
    for registered_case in registry['cases']:
        for prior_method in METHODS:
            claim=claims/(registered_case['id']+'_'+prior_method+'-comparison')
            if claim.exists() and not any(a['case_id']==registered_case['id'] and a['method']==prior_method for a in registry['attempts']):
                raise AdmissionError('Unreconciled durable claim stops further execution')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    claims=Path(claims);claims.mkdir(parents=True,exist_ok=True)
    inputs=case['inputs'];started=time.monotonic()
    row={'case_id':case['id'],'method':method,'status':'attempted','case_sha256':digest(case)}
    registry['attempts'].append(row)
    # Caller persists registry before/after orchestration. This exclusive claim
    # durably records the attempt before any execution even if registry save fails.
    # Neither source nor model may control the claim store or provenance review.
    identity=case['id']+'_'+method
    with (claims/(identity+'-comparison')).open('x') as stream:
        json.dump({'case_sha256':digest(case),'method':method,'protocol_sha256':digest(protocol)},stream)
    result={'status':'execution_error','method':method,'context_sha256':digest(packet),'worlds_attempted':0,
            'paid_requests':0,'preparation_effort_seconds':case['conventional']['effort_seconds'] if method==METHODS[0] else None}
    try:
        if method=='wheel_meta':
            if gateway_factory is None:raise AdmissionError('Explicit trusted provider factory required')
            value=run_investigation(baseline,candidate,*[inputs[k] for k in ('source','manifest','lifecycle','interface','contract','policy')],
                                    output/'investigation',claims,gateway_factory,transport='meta')
            result.update(status=value['status'],investigation=value,paid_requests=value['paid_requests_attempted'],
                          stop_required=value.get('diagnosis_status')=='provider_or_transport_error')
        else:
            controls=run_service_pair(baseline,candidate,inputs['source'],inputs['manifest'],inputs['lifecycle'],output/'lifecycle-controls',repetitions=1)
            result['lifecycle_status']=controls['status'];result['worlds_attempted']+=len(controls.get('worlds',[]))
            if controls['status']!='service_lifecycle_passed':
                result['status']=controls['status'];return result
            bundle=selection(case['conventional']['proposal'],packet,inputs['manifest'],inputs['lifecycle'],sources,inputs['interface'],inputs['contract'])
            (output/'frozen-experiment.json').write_text(json.dumps(bundle,indent=2)+'\n')
            execution=run_service_pair(baseline,candidate,inputs['source'],inputs['manifest'],inputs['lifecycle'],output/'experiment',repetitions=2,experiment=bundle)
            result.update(status=execution['status'],execution_sha256=digest(execution))
            result['worlds_attempted']+=len(execution.get('worlds',[]))
    except Exception as error:
        result.update(status='execution_error',error_type=type(error).__name__)
    finally:
        if method=='wheel_meta':
            for folder in ('lifecycle-controls','experiment'):
                p=output/'investigation'/folder/'result.json'
                if p.is_file():result['worlds_attempted']+=len(json.loads(p.read_text()).get('worlds',[]))
        result['execution_elapsed_seconds']=time.monotonic()-started
        row.update(status=result['status'],stop_required=result.get('stop_required',False))
        (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    """Register only; no live execution or provider construction from the CLI."""
    import argparse
    from preflight.petclinic_evaluation import strict_json
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',type=Path,required=True);parser.add_argument('--registry',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise AdmissionError('Output registry must be new')
    def read(path,maximum):
        with path.open('rb') as stream:raw=stream.read(maximum+1)
        if len(raw)>maximum:raise AdmissionError('Registration input budget exceeded')
        return strict_json(raw.decode())
    case=read(args.case,96*1024*1024);registry=read(args.registry,1024*1024)
    row=register(case,registry)
    with args.output.open('x') as stream:json.dump(registry,stream,indent=2)
    print(json.dumps({'registered':row['id'],'independence':row['independence'],'execution_performed':False}))


if __name__=='__main__':main()
