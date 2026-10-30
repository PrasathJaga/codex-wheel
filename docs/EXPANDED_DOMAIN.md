# Expanded amount-domain experiment

This is a separate registered experiment, not a replacement for `protocol_v1.json` or its results. U1 is an author-designed synthetic Java deduplication boundary case whose mechanism was discussed before registration. It is not an independently blind case. Its exact candidate bytes and baseline commit are pinned in `evaluation/expanded_domain_v1.json`.

Both methods may use integer minor-unit amounts 1–10000, the same wrapper, oracle and three fault actions. `C2_budgeted` selects six fixed public values and all three actions (18 plans). `C4_range` reads the source and may propose one plan, followed by a separate no-fault control, or abstain. Neither method receives outcome-driven replanning. All plans freeze before worlds. Three fresh baseline/candidate pairs execute per plan.

Unlike the original comparison, both methods use deterministic authorized tool arguments with no support-agent preflight or continuation. Only source investigation makes genuine Meta requests. Results must not be mixed with the earlier C2/C4 totals. No fresh assistant conversation is claimed. The fixed suite is budgeted rather than exhaustive across the shared domain; a source-aware non-LLM baseline is not evaluated. A win, tie, loss, abstention or error must be preserved.

Maximum: 120 worlds, six investigator requests, zero support requests, 2048 completion tokens/request (12288 output-token capacity), 100000 message characters/request, no SDK retries. Dollar cost and remaining credit balance are unknown. The dedicated workflow is manual or runs only on `hackathon/expanded-domain-live`; normal PR CI does not invoke inference.

Run from a clean pinned revision using:

```bash
python -m wheel.expanded_domain --expected-implementation-commit "$EXPECTED_IMPLEMENTATION_COMMIT"
```

The output includes registered inputs, source admission, raw request attempts, source-tool traces, frozen plans, per-world ledgers and outcomes. Runtime image/JAR hashes are recorded; complete binary closure is not exported. Execution failures stop with preserved evidence. Repair requires a separate admission and verification stage.
