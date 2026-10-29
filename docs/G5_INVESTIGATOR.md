# G5 source-grounded investigator slice

Status: implemented, live verification pending. This extends the preflight/freeze work in PR #6; it does not supersede its evidence or claim G6/G7 completion.

## Protocol

A trusted caller supplies only the Java service and Python wrapper source snapshots, plus the changed file path. Baseline/candidate source bytes and diffs are generated from the disclosed seeded mutations and bound in the run manifest. These are synthetic variants of a pinned repository commit, not independent candidate repository commits.

A genuine Meta investigator must call allowlisted `read_diff` and `read_source` tools, then `propose_experiment` or `abstain`. The mediator never opens a model-supplied filesystem path: it looks up exact keys in its in-memory source map. No shell, write, ledger, oracle, hidden label or credential tool exists. Source text is treated as untrusted data. This is a mediated interface on a trusted runner, not a hostile-code sandbox or formal prompt-injection guarantee.

The investigator generates the customer message, amount, fault bounds/action, hypothesis and exact source quotations. Public synthetic fixture choices are USD 25.00 or 75.00, order ORD-SYN-TRIAL, full-order scope. Both amounts are available in both investigations. The prompt does not name M1/M2, disclose the expected fault per mutation, or show evaluator labels. The source changes themselves are intentionally visible.

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
