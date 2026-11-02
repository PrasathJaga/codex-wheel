"""Read-only public source-pair intake; never imports or executes project code."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from preflight.petclinic_adapter import AdmissionError,digest
from preflight.petclinic_source_intake import collect_archive
from preflight.project_discovery import inspect_files


def inspect_pair(descriptor,baseline,candidate):
    repo=descriptor['repo']
    if type(repo) is not str or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):
        raise AdmissionError('Invalid public repository identity')
    files={};verified={}
    for side,raw in [('baseline',baseline),('candidate',candidate)]:
        if len(raw)>32*1024*1024:raise AdmissionError('Source archive budget exceeded')
        archive=descriptor['archives'][side]
        revision=archive['revision']
        if type(revision) is not str or not re.fullmatch(r'[0-9a-f]{40}',revision):
            raise AdmissionError('Pinned full upstream revision required')
        if archive['url']!='https://codeload.github.com/'+repo+'/tar.gz/'+revision:
            raise AdmissionError('Source URL differs from pinned public identity')
        if len(raw)!=archive['size_bytes'] or hashlib.sha256(raw).hexdigest()!=archive['sha256']:
            raise AdmissionError('Source archive identity mismatch')
        files[side]=collect_archive(raw,archive['sha256'],archive['root'])
        verified[side]={'archive_sha256':archive['sha256'],'revision':revision,
                        'discovery':inspect_files(files[side])}
    changed=[]
    for p in sorted(set(files['baseline'])|set(files['candidate'])):
        a,b=files['baseline'].get(p),files['candidate'].get(p)
        if a!=b:
            changed.append({'path':p,'kind':'added' if a is None else 'deleted' if b is None else 'modified',
                            'baseline_sha256':hashlib.sha256(a).hexdigest() if a is not None else None,
                            'candidate_sha256':hashlib.sha256(b).hexdigest() if b is not None else None})
    if [r['path'] for r in changed]!=sorted(descriptor['paths']):
        raise AdmissionError('Actual complete diff disagrees with reviewed GitHub metadata')
    return {'schema':'wheel-external-source-intake-v1','id':descriptor['id'],'descriptor_sha256':digest(descriptor),
            'repo':repo,'source_reference':descriptor['reference'],'origin':descriptor['kind'],
            'source_integrity_verified':True,'source_pair_direction':'upstream_parent_to_committed_change',
            'source':verified,'changed_files':changed,'test_paths_changed':[r['path'] for r in changed if '/test/' in r['path'] or Path(r['path']).name.startswith('test_')],
            'comparison_eligible':False,
            'blockers':descriptor['blockers'],'independent_case_preparation_verified':False,
            'project_code_executed':False,'model_requests':0,'wheel_source_exported':False,
            'limitations':['Source identity verification is not runtime validation.',
                           'Upstream authorship does not verify independent adapter preparation.',
                           'Published historical outcomes are already known, not blind discovery.']}


def read_bounded(path,maximum):
    with Path(path).open('rb') as stream:raw=stream.read(maximum+1)
    if len(raw)>maximum:raise AdmissionError('Input size budget exceeded')
    return raw


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('descriptor','baseline','candidate','output'):p.add_argument('--'+key,type=Path,required=True)
    args=p.parse_args()
    from preflight.petclinic_evaluation import strict_json
    descriptor=strict_json(read_bounded(args.descriptor,1024*1024).decode())
    report=inspect_pair(descriptor,read_bounded(args.baseline,32*1024*1024),read_bounded(args.candidate,32*1024*1024))
    with args.output.open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
    print(json.dumps({'id':report['id'],'source_integrity_verified':True,'test_paths_changed':[r['path'] for r in changed if '/test/' in r['path'] or Path(r['path']).name.startswith('test_')],
            'comparison_eligible':False,'changed_files':len(report['changed_files'])}))


if __name__=='__main__':main()
