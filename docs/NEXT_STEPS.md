# Acceptance gates (source: October 29 v3.2 master)

- G0: Public repo and event-period provenance, real pinned commits.
- G1: Java refund service, ledger and Python tool work with no fault; live HTTP + protected ledger assertion.
- G2: Buffer successful upstream response and inject downstream fault only after the verified fixture commit.
- G3: M1 Java low-amount dedup bypass; M2 Python HTTP-502 retry changes key; reproduce both with a manually frozen experiment and protected evaluator.
- G4: Genuine Meta support agent tool call and post-tool continuation.
- G5: Genuine Meta investigator reads source spans and selects source-grounded experiment; preflight before freezing.
- G6: At least three isolated A/B trials, matching source/fixture hashes, benign controls.
- G7: Measured, honest baseline comparisons, replayable evidence and three-minute demo.

No completed outcome is claimed solely by checking in code. Do not copy the historical pre-event ZIP into this public repo without a rights and secrets audit.

## G4 implementation update

The bounded Meta support-agent slice is implemented on the G4 branch; see [G4_META_RUNTIME.md](G4_META_RUNTIME.md). Live verification is pending until its dedicated Actions run is inspected. Full mocked-tool preflight, G5 investigation and G6/G7 evaluation remain outstanding.
