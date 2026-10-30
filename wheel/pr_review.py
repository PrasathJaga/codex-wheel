"""Manually invoked PR review for exact reviewed synthetic variants. No automatic triggers."""
import argparse
import json
import os
from pathlib import Path
import urllib.request

REPO = 'PrasathJaga/codex-wheel'
MARKER = '<!-- codex-wheel-reviewed-fixture-v1 -->'


def identity(pr):
    return (pr['base']['sha'], pr['head']['sha'])


def verdict(rows):
    if not rows: return 'inconclusive'
    pairs = []
    for trial in range(3):
        base = [r for r in rows if r['world']=='base' and r['trial']==trial]
        changed = [r for r in rows if r['world']=='candidate' and r['trial']==trial]
        if len(base)!=1 or len(changed)!=1: return 'inconclusive'
        pairs.append((base[0]['oracle_pass'],changed[0]['oracle_pass']))
    if pairs == [(True,False)]*3: return 'reproduced_regression'
    if pairs == [(True,True)]*3: return 'not_reproduced'
    return 'inconclusive'


def body(result, run_url):
    lines = [MARKER, '### Codex Wheel — reviewed synthetic fixture',
             '**Result: '+result['status']+'**',
             'Base: `'+result['base']+'` · Head: `'+result['head']+'`',
             'Execution: '+('not executed; input outside supported scope' if result['status']=='unsupported' else result.get('execution_mode', 'fresh deterministic counterfactuals'))+'; no new Meta investigation or repair.',
             'Supported scope: exact reviewed refund variants only.']
    for row in result.get('observed',[]):
        lines.append(f"- Trial {row['trial']+1}: baseline {row['base_minor_units']} USD minor units; candidate {row['candidate_minor_units']} USD minor units.")
    lines += ['[Run and downloadable evidence]('+run_url+')',
              'A later base/head revision invalidates this result. No automatic merge.']
    return '\n\n'.join(lines)


def publish(api, number, result, run_url):
    latest = api('GET',f'/pulls/{number}')
    if latest['state']!='open' or identity(latest)!=(result['base'],result['head']):
        result = {**result,'status':'stale','observed':[]}
    comments = []; page = 1
    while True:
        batch = api('GET',f'/issues/{number}/comments?per_page=100&page={page}')
        comments.extend(batch)
        if len(batch)<100: break
        page += 1
        if page>10: raise ValueError('Comment inventory exceeds bound')
    actor = 'github-actions[bot]'  # Publishing workflow uses only its GitHub Actions token.
    matches = [c for c in comments if c['body'].startswith(MARKER) and c['user']['login']==actor]
    if len(matches)>1: raise ValueError('Multiple owned review comments; manual reconciliation required')
    payload = {'body':body(result,run_url)}
    if matches: response=api('PATCH',f"/issues/comments/{matches[0]['id']}",payload)
    else: response=api('POST',f'/issues/{number}/comments',payload)
    return {'status':result['status'],'comment_id':response['id']}


def github_api(token):
    def api(method,path,data=None):
        # /user verifies the authenticated actor, never persisted in raw API output.
        url = 'https://api.github.com/user' if path=='/user' else 'https://api.github.com/repos/'+REPO+path
        request=urllib.request.Request(url,method=method,data=json.dumps(data).encode() if data is not None else None,
            headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=30) as response: return json.load(response)
    return api


def run(number, output, do_publish):
    api = github_api(os.environ.pop('GH_TOKEN',''))
    output=Path(output).absolute();output.mkdir(exist_ok=False)
    pr=api('GET',f'/pulls/{number}');base,head=identity(pr)
    result={'schema':'codex-wheel.pr-review.v1','pr':number,'base':base,'head':head,'status':'execution_error','new_meta_calls':0}
    try:
        if pr['state']!='open' or pr['head']['repo']['full_name']!=REPO: result['status']='unsupported'
        else:
            from wheel.intake import inspect,git
            from wheel.experiment import ROOT,run as execute
            from wheel.plan_guard import IntegrityError
            git(ROOT,'fetch','origin',base,head)
            try: admitted=inspect(ROOT,base,head,'java')
            except IntegrityError:
                try: admitted=inspect(ROOT,base,head,'python')
                except IntegrityError: admitted=None
            if admitted is None: result['status']='unsupported'
            else:
                result['admission']={k:v for k,v in admitted.items() if k not in ('java','python')}
                # Trusted fixture code executes, never a PR checkout or PR scripts.
                execute()
                records=json.loads((ROOT/'evidence/results.json').read_text())
                selected=[r for r in records if r['case']==admitted['case']]
                for row in selected:
                    side=row['world']
                    if row['java_sha256']!=admitted['source_hashes']['java'][side] or row['python_sha256']!=admitted['source_hashes']['python'][side]:
                        raise IntegrityError('Executed source differs from PR admission')
                # One intervention family; do not mix controls with breaking trials.
                action = 'REPLACE_DOWNSTREAM_STATUS_502' if admitted['case'] in ('M2','B2') else 'DROP_DOWNSTREAM_BEFORE_RESPONSE'
                chosen=[r for r in selected if action in r['label']]
                result['status']=verdict(chosen)
                result['observed']=[{'trial':i, **{side+'_minor_units':sum(e['amount_minor_units'] for e in next(r for r in chosen if r['trial']==i and r['world']==world)['effects']) for side,world in [('base','base'),('candidate','candidate')]}} for i in range(3)] if len(chosen)==6 else []
    except Exception as error:
        result.update(status='execution_error',error_type=type(error).__name__)
    run_url='https://github.com/'+REPO+'/actions/runs/'+os.environ['GITHUB_RUN_ID']
    (output/'result.json').write_text(json.dumps(result,indent=2))
    (output/'review.md').write_text(body(result,run_url))
    if do_publish:
        receipt=publish(api,number,result,run_url)
        (output/'publication.json').write_text(json.dumps(receipt,indent=2))
    if result['status']=='execution_error':raise RuntimeError('PR review execution failed; evidence preserved')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pr',type=int,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--publish',action='store_true')
    a=p.parse_args();run(a.pr,a.output,a.publish)
