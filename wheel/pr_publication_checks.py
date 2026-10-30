"""Explicit publication integration checks; no model calls or fresh counterfactuals."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.error
import zipfile
from wheel.pr_review import github_api, identity, publish, MARKER, run

SHA='a62d26ea064a3cf03db64568342d9ddc4dad4b9819b7e7c32c6708beb0d43edb'


def owned(api,number):
    return [c for c in api('GET',f'/issues/{number}/comments?per_page=100') if c['body'].startswith(MARKER) and c['user']['login']=='github-actions[bot]']


def check(mode, archive, directory, number):
    directory=Path(directory);directory.mkdir(exist_ok=True)
    api=github_api(os.environ['GH_TOKEN'])
    url='https://github.com/PrasathJaga/codex-wheel/actions/runs/'+os.environ['GITHUB_RUN_ID']
    if mode=='publish':
        raw=Path(archive).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=SHA:raise ValueError('Historical evidence archive mismatch')
        with zipfile.ZipFile(archive) as z:result=json.loads(z.read('pr-review-output/result.json'))
        if identity(api('GET',f'/pulls/{number}'))!=(result['base'],result['head']):raise ValueError('Validation pair differs from historical evidence')
        result={**result,'pr':number,'origin_pr':22,'execution_mode':'reused authenticated historical PR #22 evidence; no fresh worlds'}
        first=publish(api,number,result,url);second=publish(api,number,result,url)
        if first['comment_id']!=second['comment_id'] or len(owned(api,number))!=1:raise ValueError('Duplicate comment')
        (directory/'original-result.json').write_text(json.dumps(result,indent=2))
        (directory/'update-check.json').write_text(json.dumps({'first':first,'second':second,'owned_comments':1},indent=2))
    elif mode=='stale':
        result=json.loads((directory/'original-result.json').read_text())
        before=(result['base'],result['head'])
        for _ in range(48):
            latest=api('GET',f'/pulls/{number}')
            if latest['head']['sha']!=before[1]:break
            time.sleep(5)
        else:raise RuntimeError('No actual test head change observed within 240 seconds')
        receipt=publish(api,number,result,url)
        comments=owned(api,number)
        if receipt['status']!='stale' or len(comments)!=1 or '**Result: stale**' not in comments[0]['body']:raise ValueError('Stale publication check failed')
        (directory/'stale-check.json').write_text(json.dumps({'before':before,'after':identity(latest),'receipt':receipt},indent=2))
    elif mode=='unsupported':
        prs=api('GET','/pulls?state=open&head=PrasathJaga:hackathon/pr-publication-checks')
        if len(prs)!=1:raise ValueError('Expected one implementation PR')
        target=prs[0]['number']
        run(target,directory/'unsupported',True)
        result=json.loads((directory/'unsupported/result.json').read_text())
        if result['status']!='unsupported':raise ValueError('Unsupported input incorrectly admitted')
    elif mode=='permission':
        comments=owned(api,number)
        if len(comments)!=1:raise ValueError('Expected one validation comment')
        try:api('PATCH',f"/issues/comments/{comments[0]['id']}",{'body':comments[0]['body']})
        except urllib.error.HTTPError as error:
            if error.code!=403:raise
            (directory/'permission-check.json').write_text(json.dumps({'status':'expected_permission_denial','http_status':403}))
        else:raise ValueError('Read-only token unexpectedly allowed comment write')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['publish','stale','unsupported','permission'])
    p.add_argument('--archive',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--pr',type=int,required=True)
    a=p.parse_args();check(a.mode,a.archive,a.output,a.pr)
