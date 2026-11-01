import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluation.generic_transfer_v1.runner import verify_protocol,validate_case,register,validate_review,run_method
from preflight.generic_investigator import prepare
from preflight.petclinic_adapter import digest,AdmissionError

ROOT=Path(__file__).resolve().parents[1]


def fixture():
    original=json.loads((ROOT/'evaluation/generic_paid_integration_v1/python_violating.json').read_text())
    inputs={k:original[k] for k in ('baseline_base64','candidate_base64','source','manifest','lifecycle','interface','contract','policy')}
    inputs=copy.deepcopy(inputs);inputs['policy']['attempt_id']='unit_control_wheel_meta'
    import base64
    packet,_=prepare(base64.b64decode(inputs['baseline_base64']),base64.b64decode(inputs['candidate_base64']),
                     *[inputs[k] for k in ('source','manifest','lifecycle','interface','contract','policy')])
    operation=inputs['interface']['operations'][0]
    plan={'schema':'wheel-http-experiment-v1','interface_sha256':digest(inputs['interface']),
          'contract_sha256':digest(inputs['contract']),'actions':[{'operation':operation['id'],'body':None}]}
    case={'id':'unit_control','inputs':inputs,'conventional':{'context_sha256':digest(packet),
          'proposal':{'status':'propose','hypothesis':'Unit-only source-aware comparison packet',
                      'source_refs':operation['source_refs'],'plan':plan},
          'preparation_kind':'ai_assisted_source_aware','effort_seconds':None},
          'provenance':{'kind':'internal_authored','preparer':'unit fixture','prepared_after_protocol':digest(verify_protocol()),
                        'source_reference':'Internal unit fixture; never an evaluation case','effort_seconds':None},
          'expectation_commitment_sha256':digest({'unit_fixture':True})}
    return case


class TransferTests(unittest.TestCase):
    def test_frozen_protocol_and_empty_registry_do_not_claim_evaluation(self):
        p=verify_protocol();r=json.loads((ROOT/'evaluation/generic_transfer_v1/registry.json').read_text())
        self.assertEqual(r,{'protocol_sha256':digest(p),'cases':[],'attempts':[]})
        self.assertFalse(p['automatic_paid_execution']);self.assertEqual(p['paid_budget']['total_max_requests'],4)

    def test_same_context_and_strict_plan_admission(self):
        c=fixture();validate_case(c)
        c['conventional']['context_sha256']='0'*64
        with self.assertRaisesRegex(AdmissionError,'context differs'):validate_case(c)
        c=fixture();c['conventional']['proposal']['plan']['actions'][0]['url']='https://outside.invalid/'
        with self.assertRaises(AdmissionError):validate_case(c)

    def test_duplicate_registration_and_registration_after_attempt_rejected(self):
        c=fixture();r={'protocol_sha256':digest(verify_protocol()),'cases':[],'attempts':[]}
        row=register(c,r);self.assertEqual(row['independence'],'unverified_requires_external_review')
        with self.assertRaises(AdmissionError):register(c,r)
        r['attempts'].append({'status':'attempted'})
        with self.assertRaises(AdmissionError):register(c,r)

    def test_internal_cases_and_unverified_declarations_cannot_run(self):
        c=fixture();r={'protocol_sha256':digest(verify_protocol()),'cases':[],'attempts':[]};register(c,r)
        review={'case_sha256':digest(c),'protocol_sha256':r['protocol_sha256'],'provenance_verified':True,
                'reviewer':'separate unit reviewer','evidence_reference':'unit test only'}
        with self.assertRaisesRegex(AdmissionError,'Internal authored'):validate_review(c,r,review)
        review['provenance_verified']=False
        with self.assertRaises(AdmissionError):validate_review(c,r,review)
        with tempfile.TemporaryDirectory() as tmp,patch('evaluation.generic_transfer_v1.runner.run_service_pair',side_effect=AssertionError('Must not execute')):
            with self.assertRaises(AdmissionError):run_method(c,r,review,'source_aware_conventional',Path(tmp)/'out',Path(tmp)/'claims')

    def test_conventional_uses_same_prerequisites_and_two_paired_trials(self):
        c=fixture()
        # Synthetic trust-boundary witness only, not actual provenance evidence.
        c['provenance'].update(kind='upstream_existing_change',preparer='unit author')
        r={'protocol_sha256':digest(verify_protocol()),'cases':[],'attempts':[]};register(c,r)
        review={'case_sha256':digest(c),'protocol_sha256':r['protocol_sha256'],'provenance_verified':True,
                'reviewer':'unit reviewer','evidence_reference':'Synthetic unit witness; no external evaluation'}
        r['cases'].append({'id':'unit_java','language':'java','case_sha256':'1'*64})
        responses=[{'status':'service_lifecycle_passed','worlds':[{},{}]},
                   {'status':'confirmed_contract_violation','worlds':[{}, {}, {}, {}]}]
        with tempfile.TemporaryDirectory() as tmp,patch('evaluation.generic_transfer_v1.runner.run_service_pair',side_effect=responses) as executor:
            result=run_method(c,r,review,'source_aware_conventional',Path(tmp)/'out',Path(tmp)/'claims')
            self.assertEqual(result['status'],'confirmed_contract_violation')
            self.assertEqual(result['worlds_attempted'],6);self.assertEqual(result['paid_requests'],0)
            self.assertEqual(executor.call_args_list[0].kwargs['repetitions'],1)
            self.assertEqual(executor.call_args_list[1].kwargs['repetitions'],2)
            self.assertIn('experiment',executor.call_args_list[1].kwargs)
            with self.assertRaises(AdmissionError):
                run_method(c,r,review,'source_aware_conventional',Path(tmp)/'retry',Path(tmp)/'claims')

    def test_unchanged_pair_cannot_be_registered_as_fresh_change(self):
        c=fixture()
        # Reuse a previously admitted preserving context only to test rejection.
        preserving=json.loads((ROOT/'evaluation/generic_paid_integration_v1/python_preserving.json').read_text())
        c['inputs']={k:preserving[k] for k in c['inputs']};c['inputs']['policy']=copy.deepcopy(c['inputs']['policy'])
        c['inputs']['policy']['attempt_id']='unit_control_wheel_meta'
        with self.assertRaisesRegex(AdmissionError,'Unchanged pair'):validate_case(c)


if __name__=='__main__':unittest.main()
