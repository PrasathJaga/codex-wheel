> **Current two-domain update:** inventory investigation and bounded restoration are now integrated through PR #36. Read [TWO_DOMAIN_DELIVERY.md](TWO_DOMAIN_DELIVERY.md) and [the evidence index](TWO_DOMAIN_EVIDENCE_INDEX.json). The refund receipts below retain their own historical scope.

# Current workflow and evidence — 2026-10-31

Codex Wheel investigates a supported code change, executes a constrained counterfactual experiment, compares committed business effects, and helps verify a bounded repair. The demonstrated workflow is synthetic Java refund logic plus an unchanged Python retrying client.

## Start without making paid calls

1. Read the [fresh result on fixture PR #27](https://github.com/PrasathJaga/codex-wheel/pull/27#issuecomment-6531652287). This is a deliberately defective fixture; never merge it.
2. Open [successful v2 run 41114220238](https://github.com/PrasathJaga/codex-wheel/actions/runs/41114220238) and download `fresh-pr-cycle-v2-evidence`.
3. Check the downloaded ZIP SHA-256 before inspection:
   `0f8d0d0256b3c47541c9537a9418ba19bba6ecc7964db7cca94ca8eea291d802`.
   Use `sha256sum downloaded.zip` on Linux, or `Get-FileHash downloaded.zip -Algorithm SHA256` in PowerShell.
4. Extract locally and open `report.html` in a browser. This is a static evidence report, not a hosted live investigation UI.
5. Compare `cycle-summary.json`, `proposal.json`, `diagnosis.json`, `request-attempts.json`, and the `broken/` and `repaired/` records. Retain the original ZIP.

If GitHub artifact storage returns an egress-limit error, the report has not loaded. Retry access later or use a previously authenticated copy; do not substitute a different run or claim a successful download.

## What actually happened

| Stage | Observed result |
| --- | --- |
| Source admission | Exact reviewed M1 Java mutation; unchanged Python peer |
| Fresh Meta investigation | Three requests selected 2000 minor units and dropped a downstream post-commit response |
| Before repair | Three selected baseline trials committed one USD 20 refund each; three candidate trials committed two refunds, USD 40 each |
| No-fault control | One refund per world on baseline and candidate |
| Fresh diagnosis | One request; structured evidence references admitted |
| Fresh repair | One request proposed exact restoration of the supplied healthy idempotency condition |
| Repair checks | Six Java tests passed; 12 fresh repaired worlds passed |
| Whole cycle | Five genuine Meta requests, 31,814 provider-reported tokens, 24 fresh worlds |
| GitHub output | Result comment on fixture PR #27; no automatic repair merge |

The causal sequence is: first refund commits, response is lost, client retries, defective deduplication permits another commit. The observed excess is USD 20 in each selected failing candidate trial. Repeated trials are separate experiments, not cumulative production loss.

These worlds use deterministic execution. They contain no support-agent conversation to display. Earlier G6 archives do contain recorded Meta support-agent messages; those belong to their own runs.

No production incidence, production loss, guaranteed savings or numeric USD API cost is established by these receipts. Provider token usage is recorded; a dollar total requires verified applicable billing rates.

## Preserved failure and resource policy

[V1 run 41112435042](https://github.com/PrasathJaga/codex-wheel/actions/runs/41112435042) reproduced the failure in 12 fresh worlds, then stopped when its one diagnosis exhausted the 2048-token completion budget and returned incomplete JSON. Repair was not reached. Four calls and 22,763 reported tokens were retained.

V1 artifact SHA-256:
`eb932a3d5bd0f1a91ab3d98af45ebf251de5455baa878928b40a8cee1ed5bf79`.

V2 was separately registered after authorization: diagnosis capacity increased to 20,000 completion tokens; investigator and repair limits remained 2048 each. Both versions retain at most six investigator requests, one diagnosis, one repair, 24 worlds and zero automatic retries. V2 success does not erase V1 failure or establish a controlled token-budget comparison.

## Developer setup

From a clean checkout, use Java 21, Maven 3.9+, Python 3.11+ and Docker for sandbox worlds. Run these from the repository root:

```bash
python -m pip install -e './services/support-agent-python[test]'
python -m pytest -q tests services/support-agent-python/tests
mvn -B -f services/refund-api-java/pom.xml test
```

These commands run tests; they do not launch the paid Meta workflows. Live Java/Python tests have additional requirements described in the README and in `.github/workflows/verify.yml`.

The paid cycle additionally needs the OpenAI Python SDK used by the Meta-compatible client, `MODEL_API_KEY`, and GitHub permissions to read source and publish the result. Keep credentials out of logs and source. The registered workflows are restricted to named branches; automatic investigation on arbitrary PRs remains disabled. Do not push a run-trigger branch merely to inspect the evidence.

The current fresh cycle admits exact M1 only. An arbitrary repository change is not supported. Historical PR review/publication checks exercise unsupported and stale results separately; the successful fresh cycle does not prove all branches of publication behavior in that one run.

## Three-minute evidence walkthrough

- **0:00–0:30:** Open the PR result and state the business expectation: one authorized refund must produce one persisted refund.
- **0:30–1:15:** Show the recorded USD 20 baseline versus USD 40 candidate effects and the frozen post-commit response-loss intervention. Explain the retry sequence.
- **1:15–1:45:** Show the Meta-selected experiment, request receipts and diagnosis references. Distinguish model explanation from the independent ledger verdict.
- **1:45–2:30:** Show the proposed idempotency restoration, Java test results and the same selected/no-fault plans after repair.
- **2:30–3:00:** State the boundary: known seeded defect, healthy answer supplied, finite tested conditions. Show the preserved V1 failure and identify independent evaluation as pending.

## Usefulness evaluation still required

| Gate | Evidence required | Current status |
| --- | --- | --- |
| Unfamiliar change | Another person prepares a change within a declared supported scope, with provenance and answer withheld | Not established; current exact-M1 intake cannot support a broader claim |
| Conventional comparison | Source-aware conventional approach with comparable source, tools, execution and model budgets; record effort and all outcomes | Existing comparisons do not establish this stronger baseline |
| Fresh investigations | Freeze cases, budgets, stop rules and success criteria before calls; retain every outcome | V1/V2 integration outcomes retained; no independent transfer study |
| External onboarding | Another developer follows the clean-checkout instructions and records setup blockers and time | Not performed |
| Product usefulness | Developer records whether the finding changed a review decision and how much assistance was needed | Not measured |

For the external onboarding trial, record OS/tool versions, checkout SHA, setup time, first failing command, assistance received, time to explain the failure correctly, and whether the repair evidence is reviewable. Use the archived report first, so access and comprehension can be evaluated without new inference spending. A self-run setup check must not be labeled external onboarding.

Do not widen intake, make new superiority claims, or invent an independent participant to complete this checklist. Broader evaluation needs a separately declared scope and genuinely independent case preparation.

## Integration receipts

- PR #28 merged to master as `f3a3959ff3837494ba787fa18604d15345e5f40c`.
- PR #29 merged into its stacked base; master subsequently contains v2 at `11983813cf22feefad23d0ea359712833fabc760`.
- [Master baseline run 41125462586](https://github.com/PrasathJaga/codex-wheel/actions/runs/41125462586) completed successfully.
- Integration CI and the paid experiment are distinct receipts. Green baseline CI alone is not proof of a new Meta call.
