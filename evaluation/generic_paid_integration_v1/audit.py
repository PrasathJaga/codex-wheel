"""Replay committed integration receipts without Docker, inference or response repair."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import zipfile

from preflight.generic_investigator import prepare,selection,diagnosis,evidence_packet
from preflight.http_experiment import assess
from preflight.petclinic_adapter import digest,AdmissionError
from preflight.petclinic_pilot import cost_accounting

ROOT=Path(__file__).resolve().parent
ARCHIVE_SHA256='d1c3d479c0409874b93c72d842c867f67d9a69354ff4ae52d1c63434df14d204'


def audit(raw):
    if hashlib.sha256(raw).hexdigest()!=ARCHIVE_SHA256:raise AdmissionError('Integration artifact digest mismatch')
    record=json.loads((ROOT/'registration.json').read_text());expectations=json.loads((ROOT/'expectations.json').read_text())
    if digest(expectations)!=record['expectations_sha256']:raise AdmissionError('Expected outcomes commitment changed')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        read=lambda p:json.loads(z.read(p))
        summary=read('summary.json')
        if summary['status']!='completed' or summary['registration_sha256']!=digest(record):raise AdmissionError('Incomplete or different registration')
        if [r['case_id'] for r in summary['results']]!=[r['id'] for r in record['cases']]:raise AdmissionError('Case order changed')
        rows=[];receipts=[];worlds=0;usage={'prompt_tokens':0,'completion_tokens':0}
        for row,registered in zip(summary['results'],record['cases']):
            cid=row['case_id'];case=json.loads((ROOT/(cid+'.json')).read_text())
            if digest(case)!=registered['case_sha256']:raise AdmissionError('Case content changed')
            packet,sources=prepare(base64.b64decode(case['baseline_base64']),base64.b64decode(case['candidate_base64']),
                                   *[case[k] for k in ('source','manifest','lifecycle','interface','contract','policy')])
            result=read(cid+'/result.json')
            if result!=row['result'] or read(cid+'/policy.json')!=case['policy'] or read(cid+'/selection-input.json')!=packet:
                raise AdmissionError('Stored input/result mismatch')
            controls=read(cid+'/lifecycle-controls/result.json')
            if controls['status']!='service_lifecycle_passed' or controls['cleanup_errors']:raise AdmissionError('Lifecycle prerequisite failed')
            worlds+=len(controls['worlds'])
            response=read(cid+'/selection-response.json')
            bundle=selection(response,packet,case['manifest'],case['lifecycle'],sources,case['interface'],case['contract'])
            if bundle is not None:
                execution=read(cid+'/experiment/result.json')
                if (read(cid+'/frozen-experiment.json')!=bundle or digest(bundle)!=result['experiment_sha256']
                    or digest(execution)!=result['execution_sha256'] or execution['status']!=result['status'] or execution['cleanup_errors']):
                    raise AdmissionError('Frozen execution evidence mismatch')
                checks={c['operation']:c for c in case['contract']['checks']}
                for world in execution['worlds']:
                    for event in world['experiment']['events']:
                        if assess(event['response'],checks[event['action']['operation']])!=event['failures']:
                            raise AdmissionError('Recorded HTTP checker failures changed')
                evidence=evidence_packet(execution)
                if read(cid+'/diagnosis-evidence.json')!=evidence:raise AdmissionError('Diagnosis evidence changed')
                diagnosis(read(cid+'/diagnosis-response.json'),packet,evidence)
                worlds+=len(execution['worlds'])
            elif result.get('reason')!='model_abstained':raise AdmissionError('Abstention result changed')
            count=0
            for phase in ('selection','diagnosis'):
                name=cid+'/'+phase+'-request.json'
                if name not in z.namelist():continue
                receipt=read(name)
                if receipt['transport']!='meta' or receipt['status']!='response_received':raise AdmissionError('Unexpected provider receipt')
                count+=1;receipts.append(receipt)
                for key in usage:usage[key]+=receipt['usage'][key]
            if count!=result['paid_requests_attempted']:raise AdmissionError('Attempt count mismatch')
            rows.append({'case_id':cid,'known_expected_status':expectations[cid],'observed_status':result['status'],
                         'reason':result.get('reason'),'diagnosis_status':result['diagnosis_status'],
                         'paid_requests':count,'original_selection':response,
                         'schema_interface_hash_valid':packet['plan_tool_schema']['properties']['interface_sha256']['const']==digest(case['interface']),
                         'schema_contract_hash_valid':packet['plan_tool_schema']['properties']['contract_sha256']['const']==digest(case['contract'])})
        # Preserve the original receipt ordering for exact accounting replay.
        original_receipts=[read(n) for n in sorted(z.namelist()) if n.count('/')==1 and n.endswith('-request.json')]
        accounting=cost_accounting(original_receipts)
        if len(receipts)!=summary['paid_requests_attempted'] or accounting!=summary['cost_accounting']:raise AdmissionError('Accounting changed')
        usage['total_tokens']=sum(usage.values())
        return {'kind':'known_authored_paid_integration_audit','run_id':41346828931,'artifact_id':13099805978,
                'artifact_sha256':ARCHIVE_SHA256,'registration_sha256':digest(record),'worlds':worlds,
                'paid_requests':len(receipts),'usage':usage,'cost_accounting':accounting,'results':rows,
                'claims_supported':['real provider/schema/execution integration on three admitted known controls',
                                    'all four original outcomes retained'],
                'claims_not_supported':['unfamiliar discovery','conventional-baseline superiority','independent preparation',
                                        'general Java/Python support','persistence correctness','verified repair'],
                'python_preserving_abstention_preserved':True}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();report=audit(a.archive.read_bytes());a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'paid_requests':report['paid_requests'],'worlds':report['worlds'],'usage':report['usage']}))


if __name__=='__main__':main()
