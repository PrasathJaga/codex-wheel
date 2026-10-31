# Inventory candidate v1: existing JUnit caught the change

This is the retained conventional-test outcome, not a Meta finding.

- Healthy baseline: `128282473303e313182e5ef20a76527ff88d76a9`, with source and test hashes registered in `evaluation/inventory_candidate_v1.json`.
- Candidate: `961f71df68c0bd5ad0b1579f376eaf50dec27fe4`, fixture [PR #34](https://github.com/PrasathJaga/codex-wheel/pull/34). **Never merge this fixture.**
- The only edit removes the ACTIVE-state rejection in `InventoryStore.confirm`. Every test, ownership check, persistence operation and invariant guard is unchanged.
- [Inventory test run 41175358503](https://github.com/PrasathJaga/codex-wheel/actions/runs/41175358503) failed: 18 Java tests, 5 assertion failures, 1 error and no skips.
- Artifact 13031649758 ZIP SHA-256: `f55f912348b1b5be07c607c6d00c27c8ff303cd13985f8a4c05d6f418eb76048`. Downloaded ZIP digest and JUnit XML totals independently checked.

The controller test observed an expired reservation confirmation returning HTTP 200 instead of 409. Another test observed confirmation after release succeeding instead of rejecting. Reallocation and duplicate/concurrent confirmation paths retained their defense-in-depth checks and rejected inconsistent state with IO errors. These distinct outcomes must not be summarized as a demonstrated two-order oversell.

The Java stage failed before packaging/live Python scenarios. No live Python candidate worlds, model investigation or repair ran. The artifact's inherited name `inventory-healthy-baseline` does not make the candidate healthy; its run SHA and failing JUnit reports determine provenance.

## Decision

The frozen conventional tests already detect this mutation. Do not remove a test or safety guard, or keep searching for a mutation solely to obtain a favorable AI-only result.

A bounded inventory adapter could still demonstrate that source investigation selects an executable causal sequence and explains a known test-caught defect. Such a run would be an integration demonstration, not added coverage beyond this JUnit suite or proof that AI is necessary. Broader usefulness needs a separately declared independent case and credible source-aware comparison.

Before inference, implement and test source admission, the bounded event DSL/executor, evidence capture and model limits as a separate reviewed phase. Model credentials/cost authorization are not the blocker. No new request is justified merely by paid-call availability.
