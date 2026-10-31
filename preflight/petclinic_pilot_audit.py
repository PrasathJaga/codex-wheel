"""Offline audit of the registered v2 pilot. Never executes source or calls a model."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import zipfile

from preflight.petclinic_adapter import AdmissionError, digest, freeze_plan
from preflight.petclinic_evaluation import strict_json
from preflight.petclinic_meta_runner import validate_selection
from preflight.petclinic_pilot import CASES, METHODS, cost_accounting

ARTIFACT_SHA256 = '87e8be18858501b5f11c8dd498400b8b2b384304248666dd7b3da9ee6b35d946'
PROTOCOL_SHA256 = '15a493eceaa73c71c89a64b9e1ed15fc0e0d60f597646388f32c1838f63a282e'


def audit_archive(raw, root, expected_sha256=ARTIFACT_SHA256):
    """The caller must obtain the expected digest independently from GitHub metadata."""
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise AdmissionError('Artifact digest mismatch')
    if len(raw) > 32 * 1024 * 1024:
        raise AdmissionError('Archive too large')
    root = Path(root)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        names = [i.filename for i in infos]
        if (len(names) != len(set(names)) or len(names) > 2000
                or sum(i.file_size for i in infos) > 64 * 1024 * 1024
                or any(PurePosixPath(n).is_absolute() or '..' in PurePosixPath(n).parts or '\\' in n for n in names)):
            raise AdmissionError('Unsafe archive inventory')
        def read(name):
            return strict_json(archive.read(name).decode())
        summary = read('pilot-summary.json')
        if summary['protocol_sha256'] != PROTOCOL_SHA256 or summary['status'] != 'completed':
            raise AdmissionError('Unexpected or incomplete pilot')
        registry = read('execution-registry.json')
        registered = json.loads((root / 'evaluation/petclinic_transfer_registry_v2.json').read_text())
        if registry['cases'] != registered['cases']:
            raise AdmissionError('Case registration changed')
        matrix = [(c, m) for c in CASES for m in METHODS]
        if [(r['case_id'], r['method']) for r in summary['method_results']] != matrix:
            raise AdmissionError('Incomplete or reordered methods')
        if [(r['case_id'], r['method']) for r in registry['attempts']] != matrix:
            raise AdmissionError('Attempt registry mismatch')
        rows, receipts, worlds_total, mismatches = [], [], 0, []
        for row in summary['method_results']:
            case_id, method = row['case_id'], row['method']
            prefix = f'{case_id}/{method}/'
            result = read(prefix + 'result.json')
            record = next(r for r in registered['cases'] if r['id'] == case_id)
            case = json.loads((root / f'evaluation/petclinic_cases_v2/{case_id}.json').read_text())
            expectation = json.loads((root / f'evaluation/petclinic_cases_v2/{case_id}-expectation.json').read_text())
            if (result != row['result'] or result['case_input_sha256'] != digest(case)
                    or digest(case) != record['case_input_sha256']
                    or digest(expectation) != record['expectation_commitment_sha256']
                    or result['protocol_sha256'] != PROTOCOL_SHA256):
                raise AdmissionError('Method/case/expectation identity mismatch')
            worlds = read(prefix + 'world-index.json')
            if len(worlds) != result['worlds_attempted']:
                raise AdmissionError('World count mismatch')
            world_rows = []
            for entry in worlds:
                evidence = read(prefix + 'runtime/' + entry['id'] + '/result.json')
                if (evidence != entry['result'] or digest(evidence) != entry['evidence_sha256']
                        or evidence['side'] != entry['side'] or evidence['status'] != entry['status']
                        or evidence['plan_sha256'] != entry['plan_sha256']):
                    raise AdmissionError('World evidence changed')
                world_rows.append({'id': entry['id'], 'side': entry['side'], 'status': entry['status'],
                                   'http_statuses': [e['status'] for e in evidence['events']]})
            worlds_total += len(worlds)
            selection = None
            for phase in ('selection', 'diagnosis'):
                name = prefix + phase + '-request.json'
                if name not in names:
                    continue
                receipt = read(name)
                if receipt['transport'] != 'meta' or receipt['status'] != 'response_received':
                    raise AdmissionError('Unexpected provider receipt')
                receipts.append(receipt)
                if phase == 'selection':
                    value = strict_json(receipt['response']['choices'][0]['message']['content'])
                    payload = strict_json(receipt['request']['messages'][-1]['content'])
                    selection = {'recorded_status': value.get('status')}
                    try:
                        validate_selection(value, payload)
                        selection['admission'] = 'accepted'
                    except AdmissionError as error:
                        selection.update(admission='rejected', rejection=str(error))
                    if value.get('status') == 'propose':
                        try:
                            freeze_plan(value.get('plan'))
                            selection['plan_shape'] = 'accepted'
                        except AdmissionError as error:
                            selection.update(plan_shape='rejected', plan_rejection=str(error))
            if result['status'] == 'confirmed_violation' and expectation['expected_label'] == 'preserving':
                mismatches.append(case_id)
            rows.append({'case_id': case_id, 'method': method, 'result': result,
                         'selection_review': selection, 'worlds': world_rows})
        costs = cost_accounting(receipts)
        if len(receipts) != summary['paid_inference_requests_attempted'] or costs != summary['cost_accounting']:
            raise AdmissionError('Receipt or accounting mismatch')
        blockers = []
        if mismatches:
            blockers.append('prospective_preserving_control_violated')
        if not any(r['selection_review'] and r['selection_review']['recorded_status'] == 'propose'
                   and r['selection_review']['admission'] == 'accepted' for r in rows):
            blockers.append('no_admitted_meta_experiment')
        return {'artifact_sha256': expected_sha256, 'protocol_sha256': PROTOCOL_SHA256,
                'integrity': 'verified_against_supplied_digest_and_registered_cases',
                'evaluation_ready_for_repair_or_superiority_claim': not blockers,
                'blockers': blockers, 'expectation_mismatches': sorted(set(mismatches)),
                'worlds_attempted': worlds_total, 'paid_requests': len(receipts),
                'cost_accounting': costs, 'methods': rows,
                'limitations': ['Internal preparation; not independent or blind.',
                                'Digest verification does not prove the oracle itself correct.',
                                'No provider invoice or remaining balance verified.',
                                'No repair attempted; original cases and outcomes remain unchanged.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit_archive(args.archive.read_bytes(), args.root)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('integrity', 'blockers', 'worlds_attempted', 'paid_requests')}))


if __name__ == '__main__':
    main()
