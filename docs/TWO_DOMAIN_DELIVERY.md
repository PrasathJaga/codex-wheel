# Two-domain evidence, onboarding and evaluation

## Verified scope

The refund loop links source investigation, repeated ledger verification, referenced diagnosis and bounded restoration. The inventory loop links source-aware lifecycle investigation to a separately registered, freshly verified restoration. Both are known author-prepared synthetic cases, with healthy repair answers supplied. Neither demonstrates arbitrary PR support, unfamiliar-defect repair, production loss or general self-healing.

Refund successful cycle: five genuine Meta calls, 31,814 reported tokens, 24 fresh worlds. Inventory original investigation: one call, 8,593 tokens, 12 worlds. Inventory repair: one new call, 7,338 tokens, 24 fresh worlds; its 12 parent worlds remain historical. Do not count the embedded parent request/worlds twice. The two inventory calls total 15,931 reported tokens across separate runs.

Inventory's actual violation is an order committed after reservation expiry, not a two-order oversell. Existing unchanged JUnit caught it before Meta investigation. Refund v1's diagnosis truncation remains retained (four requests, 22,763 tokens, 12 worlds). The successful refund v2 was separately registered.

## Open the report without paid calls

The workflow `two-domain-report.yml` downloads exact archived artifacts, verifies original ZIP hashes, recomputes evidence bindings and renders a self-contained HTML dashboard. It makes no model request and runs no new business worlds. Desktop 1440 and narrow 390 verification checks include layout overflow, before/after controls, source references and explicit-assumption arithmetic.

Download `two-domain-evidence-report` from the report workflow and open `dashboard.html` locally. No model key, Java service or Docker is required to view it. The workflow preserves its own current output; its success must be checked for the exact PR/master revision being reviewed.

To regenerate from authenticated input ZIPs in a clean checkout:

```bash
python -m pip install -e './services/support-agent-python[test]'
python -m wheel.two_domain_report \
  --refund fresh-pr-cycle-v2.zip \
  --inventory inventory-repair-v1.zip \
  --failure fresh-pr-cycle-failure.zip \
  --output dashboard.html
```

The generator has fixed supported archive digests. A changed or incomplete archive is rejected; absence of access is not a passing result. GitHub egress/retention errors may prevent artifact download before any HTML loads. Use a separately authenticated preserved copy or retain the access failure.

## What to inspect

1. Refund before repair: USD 20 authorized; baseline USD 20/one effect; candidate USD 40/two effects. Response loss follows the first commit, then retry commits a second effect.
2. Refund after repair: the same selected input/intervention yields one effect in every baseline/candidate trial; controls also pass.
3. Inventory before repair: Meta selected Reserve A → Trigger expiry A → Checkout A. Baseline rejects with HTTP 409 and zero orders; candidate accepts and commits one order after expiry. Independent lifecycle verification fails.
4. Inventory after repair: restore the ACTIVE-state check; 18 unchanged Java tests and all 12 repaired worlds pass. Selected checkout is rejected and commits no order; control checkout remains valid.
5. Source references, raw responses/states/events, trial identities, original failure and provider receipts are inspectable. Model prose is interpretation; persisted effects and deterministic verification establish the outcome.

No support-agent conversation exists in these deterministic worlds. Older G6 archives do contain actual recorded model dialogue, but it is not silently reused in the two-domain report.

## Three-minute recorded-evidence walkthrough

| Time | Screen / explanation |
| --- | --- |
| 0:00–0:15 | Product expectation: investigate a change, execute a frozen experiment, verify committed effects and check a bounded repair. State that this is recorded synthetic evidence. |
| 0:15–0:45 | Refund before/after: USD 20 versus USD 40, commit → lost response → retry → second commit; healthy restoration returns to one effect. |
| 0:45–1:00 | Show actual source hypothesis/references and genuine request receipts. Distinguish Meta selection/interpretation from the ledger verdict. |
| 1:00–1:30 | Inventory selected sequence and measured zero-versus-one order after expiry. Explicitly say this is an invalid lifecycle, not overselling. |
| 1:30–2:00 | Inventory bounded repair, unchanged JUnit results and same-plan before/after verification. Explain that JUnit already caught the defect. |
| 2:00–2:15 | Observed refund excess and optional scenario assumptions. A projection is not production loss or guaranteed savings. |
| 2:15–2:30 | Preserve adverse outcomes: refund v1 truncation, candidate test failures and no outcome-seeking retries. |
| 2:30–3:00 | Disclose known cases, healthy answers supplied, finite scope and pending independent/external evaluation. Show artifact/run links and reviewable source. |

The saved video is an edited, captioned evidence walkthrough. It does not represent a live investigation taking three minutes. Refresh its version explicitly when content changes; older versions predate inventory and must not be presented as current.

## External-developer onboarding trial — pending

An actual developer other than the implementer should follow the report-viewing steps first, then optionally regenerate from a clean checkout. Do not ask them to trigger a paid branch. No participant has completed this trial at this checkpoint.

Record: participant role and prior project familiarity; OS/tool versions; checkout SHA; setup and first-report times; first failing command/access issue; exact assistance received; their explanation of baseline/candidate effects; whether they understand the repair's limits; whether the evidence would affect a review decision; and usefulness comments in their own words. Distinguish independent work from guided work. Retain unsuccessful onboarding and access failures.

The implementer's successful CI/browser checks do not count as external onboarding. No external messages, invitations or participant feedback are fabricated by this documentation.

## Independent-case evaluation — protocol preparation, not execution

Before additional inference, agree a narrow support boundary and identify an independent case preparer. Current admission accepts exact reviewed fixture bytes; a new case requires explicitly reviewed admission/oracle work. Freeze source/test identities, intended business contract, held-out answer, case count, stop rules and budgets before exposing the change to either investigator.

Use a credible source-aware conventional investigator with comparable source, diff, contract, dataset/event interface and execution access. Retain the existing unit/integration suites and measure their catches first. Record discovery/abstention/error, accepted counterexample, false positive, setup/investigation effort, execution workload and actual token usage/cost when verifiable. Preserve every outcome. A tie is informative; extra request volume is not a benefit.

Do not tune successive cases after seeing a miss to obtain an AI-only result. One synthetic second domain establishes adapter breadth, not independent transfer. Independent preparation/access is still required; no paid evaluation is silently started by these files.

## Delivery / submission review checklist

- Verify implementation PR and post-merge master runs separately; a pre-merge green run is not the merged-master result.
- Leave intentionally defective fixture PRs #27 and #34 unmerged. Preserve their exact revisions as evidence, not application changes.
- Check reviewer access to repository, report, original ZIPs and video. Private Library copies are preservation, not proof of public reviewer access.
- Keep pre-hackathon versus new source contributions and Indie Developer track disclosures accurate.
- Review current official submission requirements before submitting. The supplied participant guide states November 4, 9:00 PM EST; this file does not claim a fresh rules or deadline verification.
- No final CV-platform submission, public hosting, new external communications or repair merge is performed by the report workflow.

The next milestones after this delivery update are external onboarding and an independently prepared evaluation case. Those require real participation; they cannot be completed with a new README alone.
