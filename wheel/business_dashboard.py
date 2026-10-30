"""Static dashboard for authenticated recorded evidence; performs no inference."""
import argparse
import hashlib
import html
import io
import json
from pathlib import Path
import zipfile
from wheel.diagnosis import packet, validate, canonical, resolve
from wheel.financial_impact import observed


def esc(value): return html.escape(str(value), quote=True)
def usd(value): return f'USD {value / 100:,.2f}'


def diagnosis_record(path, digest, document):
    raw = Path(path).read_bytes()
    if len(raw) > 4 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('Diagnosis archive mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        if bundle.namelist().count('attempt.json') != 1:
            raise ValueError('Ambiguous diagnosis record')
        record = json.loads(bundle.read('attempt.json'))
    if (record['packet'] != document or record['protected_verdict'] != document['verdict']
            or record['evidence_sha256'] != hashlib.sha256(canonical(document).encode()).hexdigest()):
        raise ValueError('Diagnosis/evidence binding mismatch')
    if record['status'] in ('explained', 'abstained'):
        validate(document, record['diagnosis'])
    return record


def impact_panel(document):
    rows = observed(document)
    table = ''
    for row in rows:
        def amount(key):
            return 'Unknown' if row[key] is None else usd(row[key])
        table += '<tr><td>' + esc(row['world']) + ' / ' + str(row['trial'] + 1) + '</td><td>' + amount('authorized_minor_units') + '</td><td>' + amount('committed_minor_units') + '</td><td>' + amount('excess_minor_units') + '</td></tr>'
    sample = next((r for r in rows if r['world'] == 'candidate' and r['trial'] == 0), None)
    calculator = '<p>Projection unavailable: candidate trial 1 has no completed ledger evidence.</p>'
    if sample and sample['excess_minor_units'] is not None:
        calculator = '<h3>Optional exposure scenario</h3><p>Uses the observed excess from candidate trial 1: ' + usd(sample['excess_minor_units']) + ' per affected operation. Supply both assumptions. Estimates round to the nearest cent; half cents round up.</p><form id="exposure" data-excess="' + str(sample['excess_minor_units']) + '"><label for="operations">Operations per day (assumption)</label><input id="operations" inputmode="numeric" autocomplete="off"><label for="affected">Affected percentage (assumption, 0–100)</label><input id="affected" inputmode="decimal" autocomplete="off"><button type="submit">Calculate scenario</button></form><p id="exposure-result" role="status">No projection calculated. Production frequency is unknown.</p>'
        calculator += '<script>' + (Path(__file__).with_name('exposure_calculator.js')).read_text() + '</script>'
    return '<div class="history"><h2>Observed financial consequence</h2><p>Each row is one recorded synthetic world. Repeated trials are separate; they are not added together as production loss. Excess is max(committed − authorized, 0). An empty ledger is a shortfall, not a successful refund.</p><div class="impact-table"><table><tr><th>World / trial</th><th>Authorized</th><th>Committed</th><th>Excess</th></tr>' + table + '</table></div><details><summary>Per-world amounts and evidence pointers</summary><pre>' + esc(json.dumps(rows, indent=2)) + '</pre></details>' + calculator + '</div>'


def render(document, diagnosis, selections, historical=None):
    """Internal renderer: inputs must be authenticated and bound by CLI admission."""
    worlds = document['worlds']
    completed = [w for w in worlds if w['status'] == 'completed']
    authorized = document['plan']['fixture']['amount_minor_units']
    panels = []
    for side in ('base', 'candidate'):
        rows = sorted([w for w in completed if w['world'] == side], key=lambda w: w['trial'])
        if not rows:
            panels.append('<section><h2>' + esc(side) + '</h2><p>No completed world; amount unknown.</p></section>')
            continue
        sample = rows[0]
        effects = sample['effects']
        total = sum(e['amount_minor_units'] for e in effects)
        reply = (sample.get('model_reply') or {}).get('content')
        conversation = ('<blockquote>' + esc(reply) + '</blockquote><p>Recorded text; fresh inference is not asserted.</p>'
                        if reply else '<p class="muted">Deterministic execution — no agent conversation recorded.</p>')
        ledger = ''.join('<tr><td>' + esc(e['effect_id']) + '</td><td>' + usd(e['amount_minor_units']) + '</td></tr>' for e in effects)
        events = ''.join('<li><strong>' + esc(e['action']) + '</strong><pre>' + esc(json.dumps(e, indent=2)) + '</pre></li>' for e in sample['events'])
        panels.append('<section><h2>' + ('Baseline' if side == 'base' else 'Changed version') + '</h2>' + conversation +
            '<p class="amount">' + usd(total) + '</p><p>' + str(len(effects)) + ' persisted refund effect(s) · trial ' + str(sample['trial'] + 1) + '</p>' +
            '<table><tr><th>Ledger effect</th><th>Committed</th></tr>' + ledger + '</table><p>Effect counts across completed trials: ' +
            esc([len(w['effects']) for w in rows]) + '</p><details><summary>Recorded causal events</summary><ol>' + events + '</ol></details></section>')
    candidate = next((w for w in completed if w['world'] == 'candidate' and w['trial'] == 0), None)
    sequence = ''
    if candidate and len(candidate['effects']) == 2:
        fault = next((e for e in candidate['events'] if e['action'] in ('REPLACE_DOWNSTREAM_STATUS_502', 'DROP_DOWNSTREAM_BEFORE_RESPONSE') and e.get('commit_evidence')), None)
        if fault:
            intervention = 'HTTP 502 injected' if fault['action'] == 'REPLACE_DOWNSTREAM_STATUS_502' else 'response dropped'
            sequence = '<p><strong>First refund committed → ' + intervention + ' → retry → second refund committed.</strong></p>'
    totals = {}
    for side in ('base', 'candidate'):
        sample = next((w for w in completed if w['world'] == side and w['trial'] == 0), None)
        totals[side] = usd(sum(e['amount_minor_units'] for e in sample['effects'])) if sample else 'unknown'
    comparison = '<p><strong>Baseline: ' + totals['base'] + '<br>Changed version: ' + totals['candidate'] + '</strong></p>'
    refs = ''; explanation = '<p>No accepted explanation. Status: ' + esc(diagnosis['status']) + '</p>'
    if diagnosis['status'] in ('explained', 'abstained'):
        result = diagnosis['diagnosis']
        explanation = '<p>' + esc(result['explanation']) + '</p>'
        for index, ref in enumerate(result['references']):
            # resolve again so displayed evidence is always taken from the packet.
            value = resolve(document, ref['pointer'])
            refs += '<details id="ref-' + str(index) + '"><summary>' + esc(ref['pointer']) + '</summary><pre>' + esc(json.dumps(value, indent=2)) + '</pre></details>'
        explanation += '<nav>' + ' '.join('<a href="#ref-' + str(i) + '">Evidence ' + str(i+1) + '</a>' for i in range(len(result['references']))) + '</nav>'
    history = '<pre>' + esc(json.dumps(selections, indent=2)) + '</pre>'
    if historical is not None:
        history += '<h3>Original expanded v1 — preserved outcome</h3><pre>' + esc(json.dumps(historical, indent=2)) + '</pre>'
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Codex Wheel — Business effects</title><style>
*{box-sizing:border-box}body{margin:0;background:#0b1220;color:#e7efff;font:16px/1.6 system-ui}main{max-width:1180px;margin:auto;padding:40px 24px}h1{font-size:clamp(30px,5vw,54px);line-height:1.12;max-width:900px}h2{font-size:24px}p{max-width:960px}.eyebrow{color:#8bd5ff;letter-spacing:2px;font-size:13px}.hero,section,.diagnosis,.history{border:1px solid #324660;background:#132138;border-radius:16px;padding:24px;margin:20px 0}.hero{border-color:#ce786a}.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px}.pair section{min-width:0;margin:0}.amount{font-size:38px;font-weight:750;margin:16px 0;color:#a9ddff}.muted,small{color:#b4c2d8}form{display:grid;gap:10px;max-width:450px}input,button{font:inherit;padding:10px;border-radius:6px}button{cursor:pointer}.impact-table{overflow-x:auto}table{width:100%;border-collapse:collapse}td:last-child,th:last-child{min-width:96px;white-space:nowrap}td,th{text-align:left;padding:8px;border-bottom:1px solid #324660;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}summary,a{color:#a9ddff;cursor:pointer;overflow-wrap:anywhere}nav{display:flex;flex-wrap:wrap;gap:16px}details{margin:16px 0}blockquote{border-left:3px solid #8bd5ff;margin:0;padding:12px}li{padding:6px}code{overflow-wrap:anywhere}@media(max-width:700px){main{padding:24px 16px}.pair{grid-template-columns:1fr}.hero,section,.diagnosis,.history{padding:18px}.amount{font-size:32px}}
</style><main><p class="eyebrow">CODEX WHEEL / RECORDED SYNTHETIC EXPERIMENT</p><h1>One authorized refund.<br>What did the change actually commit?</h1>''' + '<div class="hero"><p>Business expectation: one refund of <strong>' + usd(authorized) + '</strong>.</p>' + comparison + '<p>Protected paired verdict: <strong>' + esc(document['verdict']['verdict']) + '</strong>.</p><p>Recorded intervention: <code>' + esc(document['plan']['rule']['action']) + '</code>.</p>' + sequence + '<p>Inspect the recorded events below for commit evidence and retry order.</p></div><div class="pair">' + ''.join(panels) + '</div>' + impact_panel(document) + '<div class="diagnosis"><h2>Recorded Meta diagnosis</h2><p class="muted">Interpretation with mechanically checked references; semantic review remains required. This page performs no inference.</p>' + explanation + refs + '</div><div class="history"><h2>Selection history and limitations</h2><p>Author-designed known case. Runtime repetitions do not measure independent discovery reliability. No production loss, savings, general superiority, or new repair capability is claimed.</p>' + history + '</div><details><summary>Authenticated identities and protected verdict</summary><pre>' + esc(json.dumps({'provenance': document['provenance'], 'verdict': document['verdict'], 'diagnosis_response': diagnosis.get('response_id'), 'usage': diagnosis.get('usage')}, indent=2)) + '</pre></details></main></html>'


def main():
    from wheel.evidence_export import export_archive
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('archive', 'diagnosis', 'output'): p.add_argument('--' + name, type=Path, required=True)
    for name in ('archive-sha', 'diagnosis-sha', 'plan'): p.add_argument('--' + name, required=True)
    p.add_argument('--historical', type=Path); p.add_argument('--historical-sha')
    a = p.parse_args()
    evidence = export_archive(a.archive, a.archive_sha)
    document = packet(evidence, a.plan)
    diagnosis = diagnosis_record(a.diagnosis, a.diagnosis_sha, document)
    historical = export_archive(a.historical, a.historical_sha)['selections'] if a.historical else None
    a.output.write_text(render(document, diagnosis, evidence['selections'], historical))


if __name__ == '__main__': main()
