"""One bounded paid integration launch, preserving the unchanged investigator."""
import argparse
import base64
import json
import os
from pathlib import Path

from preflight.generic_investigator import run_investigation, implementation_sha256
from preflight.petclinic_adapter import AdmissionError, digest
from preflight.petclinic_meta_runner import MetaGateway
from preflight.petclinic_pilot import cost_accounting

ROOT = Path(__file__).resolve().parent


def registered():
    record=json.loads((ROOT/'registration.json').read_text())
    if implementation_sha256()!=record['implementation_sha256']:
        raise AdmissionError('Registered investigator implementation changed')
    cases=[]
    for row in record['cases']:
        value=json.loads((ROOT/(row['id']+'.json')).read_text())
        if digest(value)!=row['case_sha256'] or value['policy']['implementation_sha256']!=record['implementation_sha256']:
            raise AdmissionError('Registered case changed')
        cases.append(value)
    return record,cases


def receipts(output):
    return [json.loads(p.read_text()) for p in sorted(Path(output).glob('*/*-request.json'))]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--initialize',action='store_true');parser.add_argument('--case-id')
    args=parser.parse_args();key=os.environ.pop('MODEL_API_KEY','')
    record,cases=registered()
    if not key:
        raise AdmissionError('Required Meta access missing; no launch')
    if args.initialize:
        if args.case_id is not None:raise AdmissionError('Initialization cannot select a case')
        args.output.mkdir(parents=True,exist_ok=False)
        summary={'kind':record['kind'],'registration_sha256':digest(record),'status':'ready','results':[]}
    else:
        summary=json.loads((args.output/'summary.json').read_text())
        if summary['status'] not in ('ready','in_progress') or summary['registration_sha256']!=digest(record):
            raise AdmissionError('Pilot stopped/completed or registration changed')
        position=len(summary['results'])
        if position>=len(cases) or cases[position]['case_id']!=args.case_id:
            raise AdmissionError('Cases must run once in registered order')
    try:
        if args.initialize:return
        if len(receipts(args.output))+2>record['max_requests']:
            raise AdmissionError('Inference budget exhausted')
        case=cases[len(summary['results'])]
        def factory(output,protocol):
            from openai import OpenAI
            client=OpenAI(base_url='https://api.meta.ai/v1',api_key=key,max_retries=0,timeout=300)
            return MetaGateway(client,output,protocol,'wheel_meta',transport='meta')
        result=run_investigation(base64.b64decode(case['baseline_base64']),base64.b64decode(case['candidate_base64']),
            *[case[k] for k in ('source','manifest','lifecycle','interface','contract','policy')],
            args.output/case['case_id'],args.output/'claims',factory,transport='meta')
        summary['results'].append({'case_id':case['case_id'],'result':result})
        current=receipts(args.output)
        if any(r.get('transport')!='meta' for r in current):raise AdmissionError('Test-double receipt in paid integration')
        if result.get('lifecycle_status')!='service_lifecycle_passed' or result['status'] in ('execution_error','baseline_invalid') or any(r.get('status')=='provider_error' for r in current):
            raise AdmissionError('Stopped on preserved infrastructure/access/baseline failure')
        summary['status']='completed' if len(summary['results'])==len(cases) else 'in_progress'
    except Exception as error:
        summary.update(status='stopped',error_type=type(error).__name__)
        raise
    finally:
        current=receipts(args.output)
        summary.update(paid_requests_attempted=len(current),cost_accounting=cost_accounting(current))
        (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        print(json.dumps({'status':summary['status'],'paid_requests_attempted':len(current)}))


if __name__=='__main__':main()
