"""Offline registration of KNOWN authored controls. No source or model execution."""
import base64
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from preflight.generic_investigator import implementation_sha256, prepare
from preflight.http_experiment_smoke import exercise
from preflight.petclinic_adapter import digest


def register(images, destination):
    destination = Path(destination)
    rows = []
    expectations = {}
    for language in ('python', 'java'):
        for violating in (False, True):
            case_id = language + ('_violating' if violating else '_preserving')
            captured = {}
            def capture(baseline, candidate, source, manifest, lifecycle, output, **kwargs):
                captured.update(baseline_base64=base64.b64encode(baseline).decode(),
                    candidate_base64=base64.b64encode(candidate).decode(), source=source,
                    manifest=manifest, lifecycle=lifecycle, interface=kwargs['experiment']['interface'],
                    contract=kwargs['experiment']['contract'])
                # Data capture only. This synthetic return is never a runtime receipt.
                return {'status':'confirmed_contract_violation' if violating else 'no_violation_observed',
                        'cleanup_errors':[], 'worlds':[]}
            with tempfile.TemporaryDirectory() as temporary, patch('preflight.http_experiment_smoke.run_service_pair', side_effect=capture):
                exercise(language, images[language], Path(temporary), violating=violating)
            policy = {'schema':'wheel-generic-investigation-policy-v1', 'attempt_id':case_id,
                'implementation_sha256':implementation_sha256(), 'source_sha256':digest(captured['source']),
                'lifecycle_policy_sha256':digest(captured['lifecycle']), 'interface_sha256':digest(captured['interface']),
                'contract_sha256':digest(captured['contract']),
                'source_paths':['server.py' if language=='python' else 'Server.java'], 'paid_execution_enabled':True}
            captured.update(case_id=case_id, language=language, policy=policy)
            prepare(base64.b64decode(captured['baseline_base64']), base64.b64decode(captured['candidate_base64']),
                    *[captured[k] for k in ('source','manifest','lifecycle','interface','contract','policy')])
            (destination/(case_id+'.json')).write_text(json.dumps(captured,indent=2)+'\n')
            rows.append({'id':case_id,'case_sha256':digest(captured)})
            expectations[case_id] = 'confirmed_contract_violation' if violating else 'no_violation_observed'
    (destination/'expectations.json').write_text(json.dumps(expectations,indent=2)+'\n')
    registration={'schema':'wheel-generic-paid-integration-registration-v1', 'cases':rows,
        'implementation_sha256':implementation_sha256(), 'max_requests':8, 'max_completion_tokens_total':80000,
        'kind':'known_authored_integration_controls', 'independent_preparer':False, 'runtime_outcomes_already_known':True,
        'images':images, 'expectations_sha256':digest(expectations),
        'frozen_runner_revision':'08672d7bc92edfa3a74cec0a4c2f1bebe501af8a',
        'control_run':41344873422,'control_artifact':13098299107,
        'control_artifact_sha256':'98644b64fe6bad2dd99f0a64037a057d1e7e2e57458b1bbeae84cf6413fab508'}
    (destination/'registration.json').write_text(json.dumps(registration,indent=2)+'\n')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--images',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();register(json.loads(a.images.read_text()),a.output)
