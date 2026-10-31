"""Authenticate archived refund/inventory loops and render a static evidence dashboard."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import tempfile

ROOT=Path(__file__).resolve().parents[1]
REFUND_SHA='0f8d0d0256b3c47541c9537a9418ba19bba6ecc7964db7cca94ca8eea291d802'
FAILURE_SHA='eb932a3d5bd0f1a91ab3d98af45ebf251de5455baa878928b40a8cee1ed5bf79'
INVENTORY_SHA='564c41a4e03d55366231f823f759fafe2db11949822909654b12841f785cb6ae'


def esc(value):return html.escape(str(value),quote=True)
def digest(raw):return hashlib.sha256(raw).hexdigest()
def read(root,name):return json.loads((root/name).read_text())
def pretty(value):return esc(json.dumps(value,indent=2))
def require(condition,message):
    if not condition:raise ValueError(message)


def pair_identity(rows,side_key):
    require(len(rows)==6,'Incomplete paired evidence')
    require({(r['trial'],r[side_key]) for r in rows}=={(t,s) for t in range(3) for s in ('base','candidate')},'Pair identity mismatch')


def inventory(root):
    from wheel import inventory_investigation as inv,inventory_repair as repair
    summary=read(root,'summary.json');lock=read(root,'repair-lock.json');sources=read(root,'source-snapshots.json')
    oracle=inv.module('two_domain_inventory_oracle',ROOT/'services/checkout-agent-python/checkout_agent/verifier.py')
    require(summary['status']=='verified_bounded_inventory_restoration' and summary['new_worlds']==24,'Incomplete inventory restoration')
    with tempfile.TemporaryDirectory() as directory:
        repair.authenticate(root/'origin-investigation.zip',Path(directory),lock['protocol'],sources,oracle,inv)
    selected=lock['selected_plan'];inv.validate(selected,sources)
    require(inv.sha(inv.encoded(selected))==summary['selected_plan_sha256']==lock['protocol']['selected_plan_sha256'],'Selected plan mismatch')
    restored=repair.apply_proposal(read(root,'repair-proposal.json'),sources[inv.SOURCE]['candidate'],sources[inv.SOURCE]['base'])
    repair_sha=digest(restored.encode())
    require(restored.encode()==(root/'restored-InventoryStore.java').read_bytes() and repair_sha==summary['repair_sha256'],'Repaired source mismatch')
    require(read(root,'repair-tests.json')=={'returncode':0,'source_sha256':repair_sha,'tests_unchanged':True},'Repair test binding')
    images=read(root,'runtime-images.json');require(all(read(root,'confinement.json').values()),'Confinement failure')
    jars={};stages={}
    for stage in ('broken','repaired'):
        stages[stage]={}
        for plan in ('selected','control'):
            rows=read(root,stage+'-'+plan+'-worlds.json');pair_identity(rows,'side')
            actions=selected['actions'] if plan=='selected' else lock['control']
            for row in rows:
                folder=root/f"{stage}-{plan}-{row['trial']}-{row['side']}"
                require(row['snapshot']==read(folder,'state.json') and row['trace']==read(folder,'action-trace.json'),'Inventory disk/trace mismatch')
                require([x['action'] for x in row['trace']]==actions,'Action drift')
                require(row['image']==images['java'],'Runtime image drift')
                key='base' if row['side']=='base' else stage+'-candidate'
                jars.setdefault(key,row['jar_sha256']);require(jars[key]==row['jar_sha256'],'Runtime JAR drift')
                try:actual=oracle.verify(row['snapshot'],row['accepted_orders'])
                except ValueError as error:require(row['status']=='contract_violation' and row['violation']==str(error),'Violation mismatch')
                else:require(row['status']=='pass' and row['verification']==actual,'Pass mismatch')
            expected='reproduced_regression' if (stage,plan)==('broken','selected') else 'not_reproduced'
            require(inv.verdict(rows)==expected,'Inventory verdict mismatch')
            stages[stage][plan]=rows
    return {'summary':summary,'lock':lock,'proposal':selected,'repair':read(root,'repair-proposal.json'),
            'stages':stages,'requests':[read(root,'parent/model-request.json'),read(root,'repair-request.json')]}


def refund(root):
    from wheel.report_visualizer import inspect
    from wheel.diagnosis import validate,canonical,packet
    summary=read(root,'cycle-summary.json');sources=read(root,'source-snapshots.json');stages={};plans={};frozen_stages={};outcomes={}
    require(summary['status']=='fresh_bounded_cycle_verified' and summary['worlds']==24,'Incomplete refund cycle')
    for stage in ('broken','repaired'):
        folder=root/stage;raw=(folder/'locked-comparison.json').read_bytes()
        frozen,groups=inspect(folder,digest(raw));plans[stage]=frozen['plans'];stages[stage]={};frozen_stages[stage]=frozen;outcomes[stage]=[]
        require(len(groups)==2,'Unexpected refund plans')
        for plan,rows,verdict in groups:
            pair_identity(rows,'world');require(all(r['status']=='completed' for r in rows),'Incomplete refund world')
            label='selected' if plan['id']=='C4-0' else 'control'
            expected='reproduced_regression' if (stage,label)==('broken','selected') else 'not_reproduced'
            require(verdict['verdict']==expected,'Refund verdict mismatch')
            stages[stage][label]=rows
            outcomes[stage].append({'id':plan['id'],'verdict':verdict})
    for before,after in zip(plans['broken'],plans['repaired']):
        require({k:v for k,v in before.items() if k!='source_hashes'}=={k:v for k,v in after.items() if k!='source_hashes'},'Refund inputs/intervention changed after repair')
        expected_hashes=json.loads(json.dumps(before['source_hashes']))
        expected_hashes['java']['candidate']=expected_hashes['java']['base']
        require(after['source_hashes']==expected_hashes,'Unexpected repaired source identities')
    java_path=next(p for p in sources if p.endswith('RefundService.java'))
    healthy=sources[java_path]['base'];restored=(root/'restored-RefundService.java').read_text()
    require(restored==healthy and digest(restored.encode())==summary['repair_sha256'],'Refund restoration bytes')
    tests=read(root,'repair-unit-tests.json');require(tests['returncode']==0 and tests['source_sha256']==summary['repair_sha256'],'Refund repair test identity')
    for row in stages['repaired']['selected']+stages['repaired']['control']:
        require(row['java_sha256']==summary['repair_sha256'],'Refund runtime source differs from repair')
    diagnosis=read(root,'diagnosis.json');require(diagnosis['status']=='explained','Refund diagnosis not admitted')
    export={'frozen':frozen_stages['broken'],'plans':outcomes['broken'],'worlds':read(root/'broken','results.json'),
            'provenance':{'activity':'fresh_current_cycle','plan_sha256':digest((root/'broken/locked-comparison.json').read_bytes())},
            'supporting_records':{'source-snapshots.json':sources},'limits':summary['limits']}
    require(packet(export,'C4-0')==diagnosis['packet'] and diagnosis['protected_verdict']==diagnosis['packet']['verdict'],'Refund diagnosis/evidence binding')
    validate(diagnosis['packet'],diagnosis['diagnosis'])
    require(digest(canonical(diagnosis['packet']).encode())==diagnosis['evidence_sha256'],'Refund diagnosis packet hash')
    return {'summary':summary,'proposal':read(root,'proposal.json'),'stages':stages,'plans':plans['broken'],
            'diagnosis':diagnosis,'requests':read(root,'request-attempts.json'),'repair':read(root,'repair-proposal.json')}


def usage(requests):
    ids=[r['response_id'] for r in requests]
    require(len(ids)==len(set(ids)),'Duplicate provider receipts')
    require(all(r.get('model')=='muse-spark-1.3' for r in requests),'Unexpected provider model')
    return {'calls':len(requests),'tokens':sum(r['usage']['total_tokens'] for r in requests),'response_ids':ids}


def load(refund_zip,inventory_zip,failure_zip):
    from wheel.repair_link import unpack
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        for label,path,expected in [('refund',refund_zip,REFUND_SHA),('inventory',inventory_zip,INVENTORY_SHA),('failure',failure_zip,FAILURE_SHA)]:
            target=root/label;target.mkdir();unpack(path,expected,target)
        r=refund(root/'refund');i=inventory(root/'inventory');failed=read(root/'failure','cycle-summary.json')
        require(failed['status']=='failed' and failed['new_model_calls']==4 and failed['worlds']==12,'Historical failure missing')
        diagnosis=read(root/'failure','diagnosis.json')
        require(diagnosis['response']['choices'][0]['finish_reason']=='length','Historical truncation mismatch')
        r['usage']=usage(r['requests']);i['usage']=usage(i['requests'])
        return {'refund':r,'inventory':i,'failed_refund':failed,'archive_hashes':{'refund':REFUND_SHA,'inventory':INVENTORY_SHA,'failed_refund':FAILURE_SHA}}


def details(title,value,identifier=''):
    return '<details'+(' id="'+esc(identifier)+'"' if identifier else '')+'><summary>'+esc(title)+'</summary><pre>'+pretty(value)+'</pre></details>'


def money(minor):return f'USD {minor//100:,}.{minor%100:02d}'
def order_count(row):
    count=len(row['snapshot']['orders'])
    return str(count)+(' order' if count==1 else ' orders')


def domain_card(name,title,subtitle,before,after,reason,sequence,refs,limits):
    body='<section class="domain" id="'+name+'"><p class="eyebrow">'+esc(name.upper())+' / VERIFIED SYNTHETIC CASE</p><h2>'+esc(title)+'</h2><p>'+esc(subtitle)+'</p>'
    body+='<div class="stage-buttons" role="group" aria-label="'+name+' verification stage"><button data-domain="'+name+'" data-stage="broken" aria-pressed="true">Before repair</button><button data-domain="'+name+'" data-stage="repaired" aria-pressed="false">After repair</button></div>'
    for stage,data in [('broken',before),('repaired',after)]:
        body+='<div data-panel="'+name+'-'+stage+'"'+(' hidden' if stage=='repaired' else '')+'><div class="comparison">'
        for label,number,description in data['cards']:
            body+='<article><h3>'+esc(label)+'</h3><p class="metric">'+esc(number)+'</p><p>'+esc(description)+'</p></article>'
        body+='</div><p class="verdict">'+esc(data['verdict'])+'</p><div class="table-scroll"><table><caption>Three selected baseline/candidate pairs · '+esc(stage)+' stage</caption><thead><tr><th>Trial</th><th>Baseline</th><th>Changed version</th></tr></thead><tbody>'
        for index,(base,candidate) in enumerate(data['trials'],1):body+='<tr><td>'+str(index)+'</td><td>'+esc(base)+'</td><td>'+esc(candidate)+'</td></tr>'
        body+='</tbody></table></div>'+details('Actual recorded trial 1: state, response and events',data['evidence'])+'</div>'
    body+='<h3>Recorded causal sequence</h3><ol class="sequence">'+''.join('<li>'+esc(step)+'</li>' for step in sequence)+'</ol>'
    body+='<h3>What Meta contributed</h3><p>'+esc(reason)+'</p><p>Recorded source-aware experiment selection and bounded repair proposal. Execution here is deterministic; no support-agent conversation is invented.</p>'
    body+=details('Exact recorded source references',refs,name+'-sources')+'<p class="notice">'+esc(limits)+'</p></section>'
    return body


def render(document):
    r=document['refund'];i=document['inventory']
    refund_views={};inventory_views={}
    plan=next(p for p in r['plans'] if p['id']=='C4-0');authorized=plan['fixture']['amount_minor_units']
    for stage in ('broken','repaired'):
        rows=r['stages'][stage]['selected'];base=next(x for x in rows if x['trial']==0 and x['world']=='base');candidate=next(x for x in rows if x['trial']==0 and x['world']=='candidate')
        total=lambda row:sum(x['amount_minor_units'] for x in row['effects'])
        trials=[]
        for trial in range(3):
            values=[next(x for x in rows if x['trial']==trial and x['world']==side) for side in ('base','candidate')]
            trials.append(tuple(money(total(x))+' · '+str(len(x['effects']))+' effect(s)' for x in values))
        refund_views[stage]={'cards':[('Authorized',money(authorized),'One full-order refund'),('Baseline committed',money(total(base)),'Verified persisted ledger'),('Changed version committed',money(total(candidate)),str(len(candidate['effects']))+' refund effect(s)')],
                             'trials':trials,'evidence':{'baseline':base,'candidate':candidate},'verdict':'Regression reproduced in 3/3 pairs' if stage=='broken' else 'Restoration passed all selected and control worlds'}
        rows=i['stages'][stage]['selected'];base=next(x for x in rows if x['trial']==0 and x['side']=='base');candidate=next(x for x in rows if x['trial']==0 and x['side']=='candidate')
        trials=[]
        for trial in range(3):
            values=[next(x for x in rows if x['trial']==trial and x['side']==side) for side in ('base','candidate')]
            trials.append(tuple(str(len(x['snapshot']['orders']))+' order(s) · '+('checkout rejected' if x['trace'][-1]['status']=='rejected' else 'checkout accepted') for x in values))
        inventory_views[stage]={'cards':[('Reservation','Expired','Checkout must be rejected'),('Baseline committed',order_count(base),'Checkout rejected'),('Changed version committed',order_count(candidate),'Checkout accepted after expiry' if stage=='broken' else 'Checkout correctly rejected')],
                               'trials':trials,'evidence':{'baseline':base,'candidate':candidate},'verdict':'Invalid lifecycle transition reproduced in 3/3 pairs' if stage=='broken' else 'Restoration passed all selected and control worlds'}
    body=domain_card('refund','One refund authorized. Two effects committed.','A lost post-commit response triggers a retry; the changed producer permits a second refund.',refund_views['broken'],refund_views['repaired'],r['proposal'].get('hypothesis',str(r['proposal'])),['First refund commits','Response is lost','Python client retries','Second refund commits'],r['proposal'].get('source_refs',r['proposal']),
                     'Known author-seeded M1. Healthy repair answer supplied. The earlier 2048-token diagnosis failed and remains preserved below.')
    body+=domain_card('inventory','Expired reservation. Accepted order.','The selected experiment tests lifecycle validity. It does not demonstrate two buyers overselling stock.',inventory_views['broken'],inventory_views['repaired'],i['proposal']['reason'],[x['op'].replace('_',' ').title()+' · buyer '+x['buyer'] for x in i['proposal']['actions']],i['proposal']['citations'],
                      'Existing unchanged JUnit already caught this defect: 18 tests, 5 failures and 1 error. No added detection coverage or AI necessity is established. Healthy repair answer supplied.')
    refund_usage=r['usage'];inventory_usage=i['usage'];excess=max(sum(e['amount_minor_units'] for e in next(x for x in r['stages']['broken']['selected'] if x['trial']==0 and x['world']=='candidate')['effects'])-authorized,0)
    index={'refund':{'run':41114220238,'artifact':13006180773,'sha256':REFUND_SHA,'worlds':24,'usage':refund_usage},'inventory':{'investigation_run':41181104497,'repair_run':41185855021,'repair_artifact':13036779161,'sha256':INVENTORY_SHA,'investigation_worlds':12,'repair_fresh_worlds':24,'historical_worlds_in_repair_archive':12,'usage':inventory_usage},'preserved_refund_failure':{'run':41112435042,'sha256':FAILURE_SHA,'calls':4,'tokens':22763,'worlds':12}}
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Codex Wheel · Verified behavioral effects</title><style>
:root{color-scheme:dark;--bg:#0b1322;--panel:#132238;--line:#344b65;--text:#edf4ff;--muted:#b6c7db;--accent:#9ddcff;--green:#a2e5c4}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 system-ui}main{max-width:1250px;margin:auto;padding:36px 28px}nav{display:flex;flex-wrap:wrap;gap:20px;padding:12px 0}a,summary{color:var(--accent)}a:focus,button:focus,summary:focus{outline:3px solid #fff;outline-offset:3px}h1{font-size:clamp(34px,4.5vw,62px);line-height:1.1;letter-spacing:-1.6px;max-width:1000px}h2{font-size:clamp(27px,3vw,40px);line-height:1.2}h3{font-size:17px}p{max-width:1000px}.eyebrow{color:var(--accent);font-size:12px;letter-spacing:2px;font-weight:700}.intro{color:var(--muted);font-size:20px}.hero,.domain,.support{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:28px;margin:26px 0}.hero{background:linear-gradient(125deg,#162e45,#132238)}.badges{display:flex;gap:12px;flex-wrap:wrap}.badges span{border:1px solid var(--line);border-radius:30px;padding:6px 12px;font-size:13px}.comparison{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:20px 0}.comparison article{min-width:0;background:#0d1a2b;padding:20px;border:1px solid var(--line);border-radius:12px}.metric{font-size:clamp(26px,3vw,40px);font-weight:750;line-height:1.2;color:var(--accent)}.verdict{color:var(--green);font-weight:650}.stage-buttons{display:flex;gap:10px;flex-wrap:wrap}button{font:inherit;border:1px solid #5c7e9f;border-radius:8px;padding:9px 16px;background:#0d1a2b;color:var(--text);cursor:pointer}button[aria-pressed=true]{background:#a6dfff;color:#102236}.sequence{display:flex;gap:12px;flex-wrap:wrap;padding-left:24px}.sequence li{padding:8px 16px 8px 4px}.notice{border-left:3px solid #edbc80;padding:12px 18px;background:#1d2c40}.table-scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;border-bottom:1px solid var(--line);padding:12px;overflow-wrap:anywhere}caption{text-align:left;color:var(--muted);padding:12px 0}details{margin:20px 0}summary{cursor:pointer;font-weight:600}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;background:#0d1a2b;padding:16px;border-radius:8px;max-height:520px;overflow:auto}code{overflow-wrap:anywhere}form{display:grid;gap:10px;max-width:450px}input{font:inherit;padding:10px;background:#0d1a2b;color:var(--text);border:1px solid #5c7e9f;border-radius:6px}[hidden]{display:none!important}footer{color:var(--muted);padding:24px 0}@media(max-width:700px){main{padding:20px 14px}.hero,.domain,.support{padding:20px}.comparison{grid-template-columns:1fr}.metric{font-size:30px}.intro{font-size:18px}th,td{padding:8px;font-size:12px}}
</style></head><body><main><header id="overview"><p class="eyebrow">CODEX WHEEL / AUTHENTICATED RECORDED EVIDENCE</p><nav aria-label="Evidence sections"><a href="#refund">Refund</a><a href="#inventory">Inventory</a><a href="#repair">Repair &amp; receipts</a><a href="#limits">Limits</a></nav><h1>What did the change actually commit?</h1><p class="intro">Source-aware investigation → frozen experiment → independent business-effect verification → bounded repair.</p><div class="badges"><span>Two synthetic domains</span><span>Actual persisted effects</span><span>Finite tested conditions</span></div><div class="hero"><h2>Success can hide a business violation.</h2><p>Refund: USD 20 authorized, USD 40 committed. Inventory: an expired reservation accepted for checkout. Both defects were restored to their supplied healthy baselines and checked again.</p><p>This report displays authenticated recordings. Opening it makes no model call, executes no service and requests no credentials.</p></div></header>'''+body+'''<section class="support" id="repair"><p class="eyebrow">REPAIR &amp; VERIFICATION</p><h2>Same experiment. Verified restoration.</h2><p>Refund: 24 fresh cycle worlds; 12 repaired worlds passed. Inventory: 24 fresh repair-run worlds; 12 repaired worlds passed. Each loop keeps its original failure and checks the selected experiment plus a happy/no-fault control.</p><p>Both repairs restore supplied healthy source. No application fix was automatically merged. The inventory defect was already caught by the unchanged JUnit suite.</p>'''+details('Refund: actual Meta repair proposal',r['repair'])+details('Inventory: actual Meta repair proposal',i['repair'])+details('Refund: evidence-referenced diagnosis',r['diagnosis']['diagnosis'])+'<h3>Genuine Meta receipts</h3><p>Refund successful cycle: '+str(refund_usage['calls'])+' calls · '+f"{refund_usage['tokens']:,}"+' tokens. Inventory investigation and repair: '+str(inventory_usage['calls'])+' distinct calls · '+f"{inventory_usage['tokens']:,}"+' tokens. These belong to separate registered runs. Token counts are provider-reported; dollar cost is not established.</p>'+details('Exact response IDs and usage',{'refund':refund_usage,'inventory':inventory_usage})+'</section><section class="support" id="impact"><h2>Observed impact and optional exposure</h2><p>Refund observed excess: <strong>'+money(excess)+'</strong> in each selected failing candidate trial. Repetitions are separate experiments, not cumulative production loss. Inventory impact is an invalid order after expiry; no monetary loss or oversold quantity is inferred.</p><form id="exposure" data-excess="'+str(excess)+'"><label for="operations">Operations per day · your assumption</label><input id="operations" inputmode="numeric" autocomplete="off"><label for="affected">Affected percentage · your assumption</label><input id="affected" inputmode="decimal" autocomplete="off"><button type="submit">Calculate estimated exposure</button></form><p id="exposure-result" role="status">No projection calculated. Production frequency is unknown.</p></section><section class="support" id="limits"><h2>What this establishes—and what remains open</h2><p>Two domain-specific integrations work on disclosed author-prepared cases. This does not establish arbitrary-PR support, independent transfer, superiority over a source-aware conventional approach, production ROI or general self-healing.</p><p>Inventory uses explicit expiry events, not physical-clock or distributed-race proof. Its unchanged Python peer runs in the trusted host harness; the producer runs in constrained Docker. Runtime binaries are identified by hashes but are not fully exported.</p><p>External developer onboarding and an independently prepared unfamiliar change remain unperformed. The next evaluation needs comparable source/tool access, frozen budgets and every outcome retained.</p><h3>Preserved adverse outcome</h3><p>Refund v1 reproduced the failure in 12 worlds but exhausted its 2048-token diagnosis cap and stopped with incomplete JSON. Four calls and 22,763 tokens were retained. The separately registered successful v2 run did not erase that failure.</p>'+details('Preserved original failure summary',document['failed_refund'])+details('Archive identities and run index',index)+'<p><a href="https://github.com/PrasathJaga/codex-wheel/actions/runs/41114220238">Refund run</a> · <a href="https://github.com/PrasathJaga/codex-wheel/actions/runs/41185855021">Inventory repair run</a></p></section><footer>Recorded synthetic evidence · No real money or customer orders · Generated from authenticated archives · 31 October 2026</footer></main><script>document.querySelectorAll("button[data-domain]").forEach(button=>button.addEventListener("click",()=>{const domain=button.dataset.domain;document.querySelectorAll("button[data-domain="+domain+"]").forEach(b=>b.setAttribute("aria-pressed",String(b===button)));document.querySelectorAll("[data-panel^="+domain+"-]").forEach(p=>p.hidden=p.dataset.panel!==domain+"-"+button.dataset.stage)}));</script><script>'+(ROOT/'wheel/exposure_calculator.js').read_text()+'</script></body></html>'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('refund','inventory','failure','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();document=load(args.refund,args.inventory,args.failure)
    args.output.write_text(render(document))


if __name__=='__main__':main()
