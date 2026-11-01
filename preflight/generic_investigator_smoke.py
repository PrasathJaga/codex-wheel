"""Authored Java/Python orchestration checks with explicit model test doubles."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from preflight.generic_investigator import run_investigation, implementation_sha256
from preflight.http_experiment_smoke import exercise
from preflight.petclinic_adapter import digest
from preflight.petclinic_meta_runner import MetaGateway


def factory(output, protocol):
    def create(**request):
        packet=json.loads(request['messages'][-1]['content'])
        refs=[{'side':side,'path':next(iter(packet[side+'_sources'])),'line_start':1,'line_end':1} for side in ('baseline','candidate')]
        if 'evidence' in packet:
            value={'summary':'The independent checker recorded '+packet['verifier_status']+'.',
                   'source_refs':refs,'evidence_refs':list(packet['evidence'])[:2],
                   'limitations':['Authored model test double; no model ability or causal discovery is established.']}
        else:
            schema=packet['plan_tool_schema']['properties']
            operation=packet['interface']['operations'][0]
            value={'status':'propose','hypothesis':'The source change may affect the approved HTTP expectation.',
                   'source_refs':refs,'plan':{'schema':'wheel-http-experiment-v1',
                   'interface_sha256':schema['interface_sha256']['const'],'contract_sha256':schema['contract_sha256']['const'],
                   'actions':[{'operation':operation['id'],'body':None}]}}
        raw={'id':'authored-test-double','model':'muse-spark-1.3',
             'choices':[{'finish_reason':'stop','index':0,'message':{'role':'assistant','content':json.dumps(value)}}]}
        return SimpleNamespace(model_dump=lambda **kwargs:raw)
    client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return MetaGateway(client,output,protocol,'wheel_meta',transport='test_double')


def selected_pair(baseline,candidate,source,manifest,lifecycle,output,*,repetitions,experiment):
    interface,contract=experiment['interface'],experiment['contract']
    # Supplied old control plan is discarded; the test-double gateway proposes
    # through the complete schema. This is orchestration, not AI discovery.
    paths=sorted({r['path'] for op in interface['operations'] for r in op['source_refs']})
    policy={'schema':'wheel-generic-investigation-policy-v1','attempt_id':'authored_control',
            'implementation_sha256':implementation_sha256(),'source_sha256':digest(source),
            'lifecycle_policy_sha256':digest(lifecycle),'interface_sha256':digest(interface),'contract_sha256':digest(contract),
            'source_paths':paths,'paid_execution_enabled':False}
    output=Path(output)
    result=run_investigation(baseline,candidate,source,manifest,lifecycle,interface,contract,policy,
                             output/'investigation',output/'claims',factory)
    assert result['transport']=='test_double' and result['paid_requests_attempted']==0
    assert result['requests_attempted']==2
    assert result['diagnosis_status']=='references_validated_not_independent_causal_proof'
    execution=json.loads((output/'investigation/experiment/result.json').read_text())
    assert result['status']==execution['status']
    return execution


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python-image',required=True);parser.add_argument('--java-image',required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    rows=[]
    with patch('preflight.http_experiment_smoke.run_service_pair',side_effect=selected_pair):
        for language,image in [('python',args.python_image),('java',args.java_image)]:
            for violating in (False,True):
                row=exercise(language,image,args.output/(language+('-violating' if violating else '-preserving')),violating=violating)
                row.update(model_transport='test_double',paid_requests=0)
                rows.append(row)
    (args.output/'summary.json').write_text(json.dumps({'kind':'authored_investigation_orchestration_controls',
                                                      'model_transport':'test_double','paid_requests':0,'results':rows},indent=2)+'\n')
    print(json.dumps(rows))


if __name__=='__main__': main()
