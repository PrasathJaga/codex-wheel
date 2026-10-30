"""Fresh bounded M1 proposal linked to authenticated historical runtime verification.

One paid request, no retries. Exact reviewed healthy restoration only. Runtime
worlds remain historical; Java tests are fresh. Does not repair U1 or arbitrary PRs.
"""
import argparse
import hashlib
import html
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
import zipfile

ORIGIN_SHA='7406e1a3387ddaf1e1df90cb1e1732aa61249843a1d0d8a49da94c7fbb0ca44f'
REPAIR_SHA='55fd03b8163b5168214ebd2cc61db48a4164d32e8a81532b65a89535e7bc1760'


def unpack(path, expected, destination):
    path=Path(path)
    if path.is_symlink() or path.stat().st_size>16*1024*1024:raise ValueError('Unsafe archive')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Archive digest mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        entries=bundle.infolist()
        if len(entries)>4096 or len({e.filename for e in entries})!=len(entries) or sum(e.file_size for e in entries)>64*1024*1024:raise ValueError('Archive inventory exceeds limits')
        for e in entries:
            p=PurePosixPath(e.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in e.filename or stat.S_ISLNK(e.external_attr>>16):raise ValueError('Unsafe archive member')
        bundle.extractall(destination)


def match_tested_source(source, lock, unit_tests):
    sha=hashlib.sha256(source.encode()).hexdigest()
    if sha!=lock['repair_sha256'] or unit_tests!={'returncode':0,'source_sha256':sha}:
        raise ValueError('Proposed source does not match tested restoration')
    return sha


def run(origin, repair, pr_evidence, output):
    from wheel import patcher, report_visualizer
    from wheel.evaluation_model import RequestLedger
    from wheel.meta_agent import MetaAgent
    output=Path(output).absolute();output.mkdir(exist_ok=False)
    status={'schema':'codex-wheel.repair-link.v1','status':'started','new_model_requests':0,
            'new_runtime_worlds':0,'historical_runtime_worlds':96,'fresh_java_tests':False,
            'origin_zip_sha256':ORIGIN_SHA,'repair_zip_sha256':REPAIR_SHA,
            'limits':['M1 only; does not repair U1','Healthy source supplied; exact restoration only',
                      'Historical runtime verification is matched by source bytes, not freshly executed',
                      'No arbitrary repair, universal correctness or automatic merge claim']}
    try:
        with tempfile.TemporaryDirectory() as directory:
            scratch=Path(directory);old=scratch/'origin';old.mkdir();fixed=scratch/'repair';fixed.mkdir()
            unpack(origin,ORIGIN_SHA,old);unpack(repair,REPAIR_SHA,fixed)
            lock=json.loads((fixed/'locked-repair.json').read_text())
            old_plan=hashlib.sha256((old/'locked-comparison.json').read_bytes()).hexdigest()
            lock_sha=hashlib.sha256((fixed/'locked-repair.json').read_bytes()).hexdigest()
            # Reuses original event/ledger/pair checks and repair-parent runtime binding.
            historical_html=report_visualizer.render(old,old_plan,repair=fixed,repair_hash=lock_sha)
            for stage in ('broken','repaired'):
                root=fixed/stage;raw=(root/'locked-comparison.json').read_bytes()
                _,groups=report_visualizer.inspect(root,hashlib.sha256(raw).hexdigest())
                rows=json.loads((root/'results.json').read_text())
                if len(rows)!=48 or any(r['status']!='completed' for r in rows):raise ValueError('Incomplete historical verification')
                if stage=='repaired' and (any(not r['oracle_pass'] for r in rows) or any(g[2]['verdict']!='not_reproduced' for g in groups)):
                    raise ValueError('Historical restoration did not pass')
                if stage=='broken' and not any(g[2]['verdict']=='reproduced_regression' for g in groups):raise ValueError('Historical failure absent')
            p=patcher.protocol();plans,view,failures=patcher.load_origin(origin,p)
            pr_root=scratch/'pr';pr_root.mkdir()
            unpack(pr_evidence,'a62d26ea064a3cf03db64568342d9ddc4dad4b9819b7e7c32c6708beb0d43edb',pr_root)
            pr_result=json.loads((pr_root/'pr-review-output/result.json').read_text())
            expected_hashes={'java':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in view[patcher.DOMAIN].items()},'python':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in view[patcher.CLIENT].items()}}
            if pr_result['status']!='reproduced_regression' or pr_result['admission']['source_hashes']!=expected_hashes:raise ValueError('PR failure source does not match repair scope')
            status['historical_pr']={k:pr_result[k] for k in ('pr','base','head')}
            status['historical_pr']['current_revision_claim']=False
            client=MetaAgent(max_calls=1).client
            ledger=RequestLedger(client,output/'request-attempts.json');ledger.persist()
            status['new_model_requests']=1
            proposal=patcher.propose(ledger.scoped('C4','investigator','repair-link-proposal'),view,failures)
            (output/'proposal.json').write_text(json.dumps(proposal,indent=2))
            restored=patcher.apply_proposal(proposal,view[patcher.DOMAIN]['candidate'],p)
            (output/'proposed-RefundService.java').write_text(restored)
            sha=match_tested_source(restored,lock,json.loads((fixed/'repair-unit-tests.json').read_text()))
            if restored.encode()!=(fixed/'repaired-RefundService.java').read_bytes():raise ValueError('Historical source bytes differ')
            patcher.admitted_tests(restored,scratch,output)
            if len(ledger.attempts)!=1:raise ValueError('Request count exceeded')
            status.update(status='linked_bounded_restoration',fresh_java_tests=True,repair_sha256=sha,
                          response_id=ledger.attempts[0].get('response_id'),usage=ledger.attempts[0].get('usage'),numeric_usd_cost=None)
            intro='<section style="border:2px solid #83c5ff;padding:24px;margin-bottom:30px"><h2>Fresh Meta proposal → fresh Java tests → matched recorded verification</h2><p>M1 baseline restoration only. The model receives healthy and broken source. Runtime evidence below is historical: 48 broken-stage worlds and 48 repaired-stage worlds. No new runtime worlds were executed; this is not the U1 repair.</p><p>Fresh proposal reason: '+html.escape(proposal['reason'])+'</p><details><summary>Fresh proposal and provenance</summary><pre>'+html.escape(json.dumps({'proposal':proposal,'verification':status},indent=2))+'</pre></details></section>'
            (output/'repair-loop.html').write_text(historical_html.replace('<main>','<main>'+intro,1))
            (output/'repair-result.md').write_text('M1 bounded restoration\n\nFresh Meta proposal and Java tests passed. Source matches the recorded healthy restoration. Historical runtime verification: 48 repaired worlds passed across eight plans; 48 broken-stage worlds preserve the original failure. No fresh runtime verification or U1 repair is claimed.\n')
    except Exception as error:
        status.update(status='failed',error_type=type(error).__name__)
        raise
    finally:
        (output/'link-status.json').write_text(json.dumps(status,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('origin','repair','pr-evidence','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.origin,a.repair,a.pr_evidence,a.output)
