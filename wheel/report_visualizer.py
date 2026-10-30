"""Static evidence dashboard; recomputes paired verdicts and escapes all source/model text."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re

from wheel.g6 import verify_events
from wheel.plan_guard import IntegrityError
from wheel.repeatability import validate_pair, summarize, POLICY
from wheel.verifier import check


def read(root,name):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+',name):raise IntegrityError('Unsafe evidence filename')
    path=root/name
    if path.is_symlink() or not path.is_file() or path.stat().st_size>32*1024*1024:
        raise IntegrityError('Missing or unsafe evidence input')
    return path.read_bytes()


def inspect(root,expected):
    root=Path(root);raw=read(root,'locked-comparison.json')
    if hashlib.sha256(raw).hexdigest()!=expected:raise IntegrityError('Frozen plan hash mismatch')
    frozen=json.loads(raw);rows=json.loads(read(root,'results.json'))
    if len(rows)>156 or len(frozen['plans'])>26:raise IntegrityError('Inventory exceeds bound')
    manifest={**frozen,'plan_hash':expected,'policy':POLICY};ids=[p['id'] for p in frozen['plans']]
    if len(ids)!=len(set(ids)) or any(r['plan_id'] not in ids for r in rows):raise IntegrityError('Plan inventory mismatch')
    groups=[]
    for p in frozen['plans']:
        records=[r for r in rows if r['plan_id']==p['id']]
        for trial in range(3):
            base=[r for r in records if r['trial']==trial and r['world']=='base']
            candidate=[r for r in records if r['trial']==trial and r['world']=='candidate']
            if len(base)==len(candidate)==1 and base[0]['status']==candidate[0]['status']=='completed':
                validate_pair(base[0],candidate[0],p,manifest)
                for row in base+candidate:
                    if row['oracle_pass'] is not check(row['effects'],p['fixture']):raise IntegrityError('Oracle/effect disagreement')
                    verify_events(row['events'],row['effects'],p['rule'],row['transport_errors'])
                    disk=[line.split('\t') for line in read(root,row['label']+'.tsv').decode().splitlines()]
                    expected_rows=[[e['effect_id'],e['order_id'],str(e['amount_minor_units']),e['currency'],e['refund_scope'],e['idempotency_key_sha256'],e['committed_at']] for e in row['effects']]
                    if disk!=expected_rows:raise IntegrityError('Ledger/record disagreement')
        groups.append((p,records,summarize(records)))
    return frozen,groups


def esc(value):return html.escape(str(value),quote=True)

def pretty(value):return esc(json.dumps(value,indent=2))

def money(amount):return f'{amount//100}.{amount%100:02d}'


def card(p,rows,outcome,proposal=None):
    columns=[]
    for side in ('base','candidate'):
        sample=next((r for r in rows if r['trial']==0 and r['world']==side),None)
        if sample is None:
            columns.append('<section><h4>'+esc(side)+'</h4><p>Missing world</p></section>');continue
        effects=sample.get('effects',[]);total=sum(e['amount_minor_units'] for e in effects)
        message=(sample.get('model_reply') or {}).get('content')
        chat=('<blockquote>'+esc(message)+'</blockquote><small>Recorded genuine Meta continuation</small>' if message else
              '<p class="muted">Deterministic tool execution. No new model reply.</p>')
        ledger=''.join('<tr><td>'+esc(e['effect_id'])+'</td><td>USD '+money(e['amount_minor_units'])+'</td></tr>' for e in effects)
        columns.append('<section><h4>'+esc(side.title())+'</h4>'+chat+'<p class="total">Committed USD '+money(total)+'</p><table><tr><th>Committed effect</th><th>Amount</th></tr>'+ledger+'</table></section>')
    counts={s:[len(r.get('effects',[])) for r in sorted(rows,key=lambda r:r['trial']) if r['world']==s] for s in ('base','candidate')}
    rationale=''
    if proposal:
        refs=''.join('<p class="identity">'+esc(ref['path'])+' · '+esc(ref['version'])+' · lines '+str(ref['start_line'])+'–'+str(ref['end_line'])+'</p><pre>'+esc(ref['quote'])+'</pre>' for ref in proposal.get('source_refs',[]))
        rationale='<details><summary>Recorded hypothesis and exact source citations</summary><p>'+esc(proposal.get('hypothesis',''))+'</p>'+refs+'</details>'
    return '<article><header><h3>'+esc(p['id'])+'</h3><span class="'+('bad' if outcome['verdict']=='reproduced_regression' else 'muted')+'">'+esc(outcome['verdict'])+'</span></header><p>'+esc(p['case'])+' · Authorized USD '+money(p['fixture']['amount_minor_units'])+' · '+esc(p['rule']['action'])+'</p><div class="pair">'+''.join(columns)+'</div><p>Effects across three paired trials: '+esc(json.dumps(counts))+'</p>'+rationale+'<details><summary>Frozen input and recomputed verdict</summary><pre>'+pretty({'plan':p,'verdict':outcome})+'</pre></details></article>'


def panel(title,root,expected,kind):
    frozen,groups=inspect(root,expected)
    selected=[g for g in groups if g[0]['mode']=='selected' and g[0]['id'].startswith('C4')]
    if not selected:selected=[g for g in groups if g[2]['verdict']=='reproduced_regression']
    rest=[g for g in groups if g not in selected]
    selection=frozen.get('selection',frozen.get('selections',[]))
    note={'comparison':'Known synthetic cases with unequal method budgets. Runtime outcomes and selection coverage are shown below.',
          'expanded':'Author-designed amount challenge. Both methods share the same input domain. Source selection can remain inconclusive when proposal validation fails.',
          'repair':'Bounded restoration to reviewed healthy source. Original arguments and fault rules are reused; source hashes identify the intentional repaired candidate. No population repair-success claim.'}[kind]
    methods={}
    for plan,records,outcome in groups:
        method=plan.get('method',plan['id'].split('-')[0])
        entry=methods.setdefault(method,{'plans':0,'worlds':0,'verdicts':{}})
        entry['plans']+=1;entry['worlds']+=len(records)
        verdict=outcome['verdict'];entry['verdicts'][verdict]=entry['verdicts'].get(verdict,0)+1
    counts='<table><tr><th>Method</th><th>Plans / worlds</th><th>Plan outcomes</th></tr>'+''.join('<tr><td>'+esc(k)+'</td><td>'+str(v['plans'])+' / '+str(v['worlds'])+'</td><td>'+esc(json.dumps(v['verdicts']))+'</td></tr>' for k,v in methods.items())+'</table>'
    if isinstance(selection,list):
        excluded=[e for e in selection if e.get('status')!='accepted']
        if excluded:counts+='<p>Selections without accepted runtime plans: '+esc('; '.join(str(e.get('method',''))+' '+str(e.get('case',''))+': '+str(e.get('status')) for e in excluded))+'</p>'
    if isinstance(selection,dict) and selection.get('status')!='accepted':
        counts+='<p class="bad">C4 selection: '+esc(selection.get('status'))+'; zero accepted plans and zero worlds.</p>'
    def draw(group):
        plan=group[0]
        entries=selection if isinstance(selection,list) else [selection]
        proposal=next((e.get('proposal') for e in entries if e.get('proposal') and (e.get('id','') and plan['id'].startswith(e['id']) or plan.get('method')=='C4_range')),None)
        return card(*group,proposal=proposal)
    return '<div class="dataset"><h2>'+esc(title)+'</h2><p>'+esc(note)+'</p>'+counts+'<p class="identity">Implementation '+esc(frozen['commit'])+'<br>Frozen-plan SHA-256 '+esc(expected)+'</p><details><summary>Selection record, including rejected or absent plans</summary><pre>'+pretty(selection)+'</pre></details>'+''.join(draw(g) for g in selected)+'<details><summary>All '+str(len(rest))+' additional plans and controls</summary>'+''.join(draw(g) for g in rest)+'</details></div>'


def render(comparison,comparison_hash,expanded=None,expanded_hash=None,repair=None,repair_hash=None):
    panels=[panel('Recorded source-guided discovery',Path(comparison),comparison_hash,'comparison')]
    if expanded:panels.append(panel('Expanded-domain challenge',Path(expanded),expanded_hash,'expanded'))
    if repair:
        root=Path(repair);raw=read(root,'locked-repair.json')
        if hashlib.sha256(raw).hexdigest()!=repair_hash:raise IntegrityError('Repair lock mismatch')
        frozen=json.loads(raw);proposal=json.loads(read(root,'proposal.json'))
        panels.append('<div class="dataset"><h2>Meta-proposed bounded repair</h2><p>The model received healthy and broken source plus recorded failure evidence. Admission permits only exact restoration of reviewed healthy source.</p><pre>'+esc(read(root,'proposed.patch').decode())+'</pre><p>'+esc(proposal['reason'])+'</p></div>')
        for stage in ('broken','repaired'):
            raw=read(root/stage,'locked-comparison.json');stage_frozen=json.loads(raw)
            expected_plans=json.loads(json.dumps(frozen['plans']))
            for item in expected_plans:
                item['method']=stage
                if stage=='repaired':item['source_hashes']['java']['candidate']=frozen['repair_sha256']
            if stage_frozen['plans']!=expected_plans:raise IntegrityError('Repair stage plan drift')
            panels.append(panel('Repair verification: '+stage,root/stage,hashlib.sha256(raw).hexdigest(),'repair'))
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Codex Wheel — Verified business effects</title><style>
:root{color-scheme:dark}body{background:#0b1120;color:#eaf0fb;font:16px/1.55 system-ui;margin:0 auto;max-width:1280px;padding:40px}h1{font-size:clamp(32px,5vw,58px);line-height:1.08;letter-spacing:-1px;max-width:950px}h2{font-size:28px}h3{font-size:18px}h4{font-size:19px;margin-top:0}.eyebrow{letter-spacing:3px;color:#83c5ff}.intro{max-width:900px;color:#bac8dc}.dataset{margin:50px 0;border-top:1px solid #33445d;padding-top:25px}article{background:#152137;border:1px solid #344966;padding:24px;border-radius:14px;margin:22px 0}header{display:flex;justify-content:space-between;gap:20px;align-items:center}.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px}section{min-width:0;background:#0d1728;border-radius:8px;padding:18px}.total{font-size:25px;font-weight:700}.bad{color:#ffaba5}.muted,small,.identity{color:#a8b9d2}.identity{font:12px/1.8 monospace;overflow-wrap:anywhere}blockquote{margin:10px 0;border-left:3px solid #84bfff;padding:12px;background:#1b2b44}table{width:100%;border-collapse:collapse;font-size:12px}td,th{text-align:left;padding:8px;border-bottom:1px solid #344966;overflow-wrap:anywhere}pre{font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere}details{margin:15px 0}summary{cursor:pointer;color:#a6ccff}.pill{display:inline-block;border:1px solid #4a6589;padding:6px 12px;border-radius:99px;margin:4px}@media(max-width:700px){body{padding:20px}.pair{grid-template-columns:1fr}header{display:block}}
</style><main><p class="eyebrow">CODEX WHEEL / SYNTHETIC REFUND EVIDENCE</p><h1>The agent says “refund complete.”<br>Did the business effect happen once?</h1><p class="intro">Source-guided experiments expose failures hidden behind a successful tool response. The protected evaluator counts committed effects against the authorized amount.</p><p><span class="pill">Recorded model activity</span><span class="pill">Recomputed paired verdicts</span><span class="pill">Actual persisted ledger rows</span></p><p class="intro">This static report displays archived evidence. It does not execute a model. Effect rows, oracle values, post-commit events and pair identities are checked when the report is generated. Results cover disclosed synthetic experiments; they do not establish general accuracy, security or production reliability.</p>'''+''.join(panels)+'</main></html>'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('comparison','expanded','repair'):p.add_argument('--'+name,type=Path,required=name=='comparison')
    for name in ('comparison-hash','expanded-hash','repair-hash'):p.add_argument('--'+name,required=name=='comparison-hash')
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.write_text(render(a.comparison,a.comparison_hash,a.expanded,a.expanded_hash,a.repair,a.repair_hash))
