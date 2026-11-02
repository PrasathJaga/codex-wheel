"""Assemble the submission report from authenticated, independently checked archives."""
import argparse
import html
import json
from pathlib import Path

from wheel.two_domain_report import load,render
from evaluation.generic_paid_integration_v1.audit import audit


def build(refund,inventory,failure,generic,output):
    document=load(Path(refund),Path(inventory),Path(failure))
    generic_report=audit(Path(generic).read_bytes())
    r=document['refund'];selected=next(p for p in r['plans'] if p['id']=='C4-0')
    row=next(w for w in r['stages']['broken']['selected'] if w['world']=='candidate' and w['trial']==0)
    assert row['model_reply'] is None and row['continuation']=='no_model_calls'
    authorized=selected['fixture']['amount_minor_units']
    committed=sum(e['amount_minor_units'] for e in row['effects'])
    summary={'schema':'codex-wheel.submission-evidence.v1','assembled_on':'2026-11-02',
       'evidence_source_revision':'192e34fbb1905f0516c2bf50bd33a9cbf2d7697c','archives':document['archive_hashes'],
       'refund':{'fixture_pr':27,'authorized_minor_units':authorized,'candidate_committed_minor_units':committed,
          'observed_excess_minor_units':committed-authorized,'recorded_receipt':row['receipt'],
          'paired_trials':3,'fresh_worlds':24,'provider_usage':r['usage'],'repair':'supplied_healthy_baseline_restoration'},
       'inventory':{'fresh_repair_worlds':24,'provider_usage':document['inventory']['usage'],
          'repair':'supplied_healthy_baseline_restoration','unchanged_JUnit_already_caught_defect':True},
       'generic_meta':{'requests':generic_report['paid_requests'],'worlds':generic_report['worlds'],
          'usage':generic_report['usage'],'results':[{'case':v['case_id'],'status':v['observed_status'],'reason':v['reason']} for v in generic_report['results']],
          'scope':'known_authored_HTTP_controls'},
       'external_onboarding':'not_completed','unfamiliar_comparative_evaluation':'not_completed',
       'assembly_model_requests':0,'assembly_business_worlds':0}
    page=render(document)
    money=lambda n:f'USD {n/100:.2f}'
    receipt='''<section class="support" id="receipt-story"><p class="eyebrow">THE REVIEW QUESTION</p>
<h2>The API receipt is not the whole outcome.</h2><div class="comparison">
<article><h3>Authorized</h3><p class="metric">%s</p><p>One refund</p></article>
<article><h3>Recorded API receipt</h3><p class="metric">%s</p><p>Status: committed</p></article>
<article><h3>Persisted ledger</h3><p class="metric">%s</p><p>Two committed effects</p></article></div>
<p>First commit → lost response → unchanged client retries → second commit. The independent verifier checks the ledger.</p>
<p class="notice">These worlds are deterministic execution. The receipt is an actual tool result; no agent conversation is invented.</p>
<p><a href="https://github.com/PrasathJaga/codex-wheel/pull/27#issuecomment-6531652287">Inspect the fixture PR result</a> · <a href="https://github.com/PrasathJaga/codex-wheel/actions/runs/41114220238">Inspect the original investigation and repair run</a>. The intentionally defective fixture PR is evidence, not a merge recommendation.</p></section>'''%(money(authorized),money(row['receipt']['committed_minor_units']),money(committed))
    page=page.replace('<section class="domain" id="refund">',receipt+'<section class="domain" id="refund">',1)
    rows=''.join('<tr><td>'+html.escape(v['case_id'].replace('_',' '))+'</td><td>'+html.escape(v['observed_status'])+'</td><td>'+str(v['paid_requests'])+'</td></tr>' for v in generic_report['results'])
    appendix='''<section class="support" id="generic-meta"><p class="eyebrow">ADDITIONAL VERIFIED INTEGRATION</p><h2>One schema. Java and Python.</h2>
<p>Seven real Meta requests across four known HTTP controls. Three admitted experiments; one preserved abstention. This is integration evidence, not unfamiliar discovery.</p>
<div class="table-scroll"><table><thead><tr><th>Known control</th><th>Actual outcome</th><th>Paid requests</th></tr></thead><tbody>'''+rows+'''</tbody></table></div>
<p>Python preserving remains inconclusive. Its recorded hash rationale was mistaken; no correction request or outcome-seeking retry followed. All three admitted diagnoses have validated source/evidence references, which alone do not prove causal reasoning quality.</p>
<p><a href="https://github.com/PrasathJaga/codex-wheel/actions/runs/41346828931">Original integration run</a> · <a href="https://github.com/PrasathJaga/codex-wheel/blob/master/docs/GENERIC_PAID_INTEGRATION_V1.md">Receipts and scope</a></p></section>'''
    page=page.replace('<section class="support" id="limits">',appendix+'<section class="support" id="limits">',1)
    page=page.replace('What did the change actually commit?','A successful response can hide a broken business outcome.')
    page=page.replace('</nav>','<a href="#receipt-story">PR story</a><a href="#generic-meta">Generic Meta results</a><a href="SUBMISSION.md">Reviewer guide</a></nav>',1)
    page=page.replace('</body>','<p style="padding:0 28px 24px;color:#b6c7db">Submission package assembled 2 November 2026 · Recorded evidence · No inference or business execution occurs when viewing.</p></body>')
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    (output/'index.html').write_text(page)
    (output/'evidence.json').write_text(json.dumps(summary,indent=2)+'\n')
    (output/'generic-integration-audit.json').write_text(json.dumps(generic_report,indent=2)+'\n')
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('refund','inventory','failure','generic','output'):p.add_argument('--'+key,required=True)
    a=p.parse_args();s=build(a.refund,a.inventory,a.failure,a.generic,a.output)
    print(json.dumps({'status':'authenticated_submission_report_built','assembly_model_requests':0,'refund_excess_minor_units':s['refund']['observed_excess_minor_units']}))
