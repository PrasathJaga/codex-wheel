# G5 source-grounded investigator slice

Status: implemented, live verification pending. This extends the preflight/freeze work in PR #6; it does not supersede its evidence or claim G6/G7 completion.

## Protocol

A trusted caller supplies only the Java service and Python wrapper source snapshots, plus the changed file path. Baseline/candidate source bytes and diffs are generated from the disclosed seeded mutations and bound in the run manifest. These are synthetic variants of a pinned repository commit, not independent candidate repository commits.

A genuine Meta investigator must call allowlisted `read_diff` and `read_source` tools, then `propose_experiment` or `abstain`. The mediator never opens a model-supplied filesystem path: it looks up exact keys in its in-memory source map. No shell, write, ledger, oracle, hidden label or credential tool exists. Source text is treated as untrusted data. This is a mediated interface on a trusted runner, not a hostile-code sandbox or formal prompt-injection guarantee.

The investigator generates the customer message, amount, fault bounds/action, hypothesis and exact source quotations. Under policy source-tools-high-value-v2, the Java-change fixture offers USD 25.00 or 75.00; the Python-change fixture permits USD 75.00 only, enforcing the architecture's high-value M2 requirement. Order ORD-SYN-TRIAL and full-order scope are fixed. M2 amount is therefore a public eligibility constraint, not an independently discovered amount. The prompt does not name M1/M2, disclose the expected fault per mutation, or show evaluator labels. The source changes themselves are intentionally visible.

Validation requires the diff to have been read, citations to actually read changed-candidate and unchanged-peer source, exact quote/span matching, bounded text, valid public amount and an allowlisted fault whose bounds include it. Exact quotations establish source binding, not semantic correctness of the hypothesis. The independent runtime evidence remains necessary.

Both proposals are accepted before mocked-tool preflights, plan freeze and any world execution. Support-agent prompts/tool schema stay fixed apart from the generated customer message. Real support-agent selection must match the trusted fixture authorization. No hand-selected fallback plan is substituted if investigation/preflight fails.

The runner executes each accepted proposal unchanged in baseline/candidate, retaining the protected ledger oracle. It records `observed_regression_one_trial`, `no_regression_observed_one_trial` or `inconclusive` from actual outcomes. PASS_THROUGH and non-discriminating valid plans are permitted; neither validator nor runner forces the model to “win.” There is no post-outcome adaptation.

## Budgets and evidence

- At most six investigator requests per case / twelve total, 2,048 completion tokens each, zero SDK retries; at most three rejected proposals per case before stopping.
- At most six support-agent requests, 1,024 completion tokens each. Total cap: eighteen requests per workflow execution.
- Read-only tool responses, accepted/rejected proposals, request/response IDs, model identity, usage, source snapshots, preflight records, locked inputs, raw world evidence and independent oracle results are retained.
- Paid workflow runs only by explicit dispatch or code changes on `hackathon/g5-investigator`. PR/master pushes do not spend credits. It is separate from the G4 workflow.
- Offline fake-client tests exercise mediation and rejection only; they are not real inference evidence.

## Limits and next gates

Only the two disclosed seeded changes are investigated, one paired trial each. There are no blind holdouts or measured generalization claims. The known architecture already describes these defects; actual source-grounded calls must not be portrayed as proof of novel discovery. No superiority over deterministic competitors is measured. G6 repeated live trials/benign and partial-refund controls, stronger isolation, independent candidate-commit intake, portable replay and G7 C0/C2/C4 evaluation/demo remain outstanding. Preflight failure stops this slice rather than invoking a source-grounded repair loop.

Provider tool protocol: https://dev.meta.ai/docs/tool-calling (automatic tool choice, full assistant/tool history, bounded client-side execution).


## First observed run: mechanism demonstrated, M2 fixture mismatch

Commit 3ce64b33a602d995a8239aa050051e77e941f3c7, Actions [40874181663](https://github.com/PrasathJaga/codex-wheel/actions/runs/40874181663), artifact 12898160249. The first policy exposed both USD 25 and 75 for both cases. The investigator selected USD 25/drop for M1 and USD 25/502 for M2. Both pairs produced one baseline effect and two candidate effects, with protected oracle true/false and restart recovery. However, M2 did not meet v3.2's prescribed high-value fixture. This run is not claimed as full conformance with that design.

There were 10 genuine investigator generations plus 6 support-agent generations, with 45,599 and 5,299 provider-reported tokens respectively. Three rejected proposals and their actual correction history remain in the trace. ZIP SHA-256: 5c204703aa2979c02248a26d33e0a710aac76054e80d73ce73b4aeaa827b32a8. Plan SHA-256: c44ba1b34321fa03f3738686c667540ad873d81ce5320da814cad3a076088a45.

The v2 fixture policy enforces the already-documented M2 high-value constraint before proposal acceptance. This creates a new run/manifest; the original evidence is not rewritten or relabeled. It is a conformance correction, not evidence of better selection performance. The actual fault remains freely selected from the allowlist, including PASS_THROUGH. V2 execution is pending.
