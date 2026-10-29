# G6 repeatability and controls

Implementation branch: `hackathon/g6-repeatability-controls`, based on verified master `ec55072fede610c26265e9660828f9530cf1a4f6` (PR #7 merged; master run 40876333556 passed). This document records the implementation protocol; bounded runtime results are recorded below from inspected Actions evidence.

## Predeclared protocol

`python -m wheel.g6` requires Docker, Java 21/Maven, Python and a genuine `MODEL_API_KEY`. It refuses a dirty tracked checkout or workflow/revision mismatch. It checks container availability/confinement and builds copied Java variants before spending model credits. There is no fallback to host execution, manual breaking plans or fake inference.

A genuine Meta investigator separately reads M1/M2/B1/B2 sources and proposes experiments or abstains. Its total request budget is 24, with the existing six-turn limit per investigation and source/citation gates retained. Labels are not sent to the investigator. M2/B2 retain the disclosed high-value public eligibility constraint. These remain known seeded cases, not a blind benchmark.

An explicit benign abstention is preserved. The predeclared benign stress control then inherits the corresponding M1/M2 proposal **before any world executes**, with its origin recorded. It is never described as the benign investigator's accepted proposal. Budget exhaustion, invalid-proposal exhaustion and other model errors do not take that fallback. A breaking-case abstention stops the run and records its stage.

All four customer triggers undergo genuine support-agent selection and side-effect-free mocked-tool preflight. Seeds preserve provider-compatible history and tool-call IDs; generated retry keys remain inside the actual wrapper. Plans, sources, peer hashes, authorization fixtures, source evidence, oracle code, policy, immutable runtime image IDs, built JAR hashes and three-trial count are locked before differential execution.

Each selected plan and a corresponding no-fault control receive three fresh baseline/candidate pairs: up to 8 plans, 24 pairs, 48 worlds. Each world receives a new ledger, producer process, fault gateway, wrapper container and evaluator token; graceful restart is verified inside that world's state only. The support-agent budget is at most 52 requests: four initial selections plus one genuine continuation per world. Initial tool-selection variability is held fixed; this does not measure independent investigator or initial-agent resampling reliability.

All outcomes are retained. Stable 3/3 baseline-pass and 3/3 candidate-fail signatures are required for `reproduced_regression`. Mixed signatures/results are `inconclusive`; failed baselines cannot establish a regression. Missing/failed execution or continuation is explicit. Model wording and expected mutation labels never decide the verdict. Accepted pass-through or ineffective rules are allowed; they can return `not_reproduced`, which never means safe to merge.

## Isolation and its limits

The trusted host owns Docker orchestration, the Meta key, frozen evidence, oracle and fixture expectations. The Python wrapper runs non-root with no network, read-only root, dropped capabilities, no-new-privileges, CPU/memory/PID bounds and a bounded tmpfs. Its only mounts are the candidate Python file, trusted worker and a Unix broker socket. The broker permits only bounded `POST /refunds`, strips unrelated headers and forwards only to the fixed local gateway. It denies the evaluator route and arbitrary destinations. The Meta SDK/client is not mounted.

The Java producer runs in a separate constrained container on an internal Docker network. Only its JAR and its fresh state directory are mounted; the trusted Linux runner reaches the producer directly at its internal bridge address; no producer port is published. The producer necessarily owns its synthetic ledger and evaluator token. The host independently compares ledger bytes to the protected HTTP snapshot and verifies commit-before-fault observations. Root filesystem, capability, privilege, network, environment and host-file-access probes run before paid calls. Actual image IDs are pinned for all worlds in that run; mutable image tags are resolved at setup, not silently reused across trials.

This materially strengthens isolation over same-host subprocess environment filtering. It is **not** a separate tamper-proof database, hostile-kernel isolation certification, hermetic build, power-loss guarantee or proof that malicious producer code cannot forge its own ledger. Builds execute trusted synthetic source on the host. Dependency ranges/image tags may resolve differently across runs; resolved images, dependency versions and JAR hashes are archived.

## Scope counterexamples

`check_operations` has offline counterexamples showing two authorized partial refunds on one order are legitimate when allocated to distinct authorization IDs. Duplicate, missing, misallocated and wrong-amount effects fail. These tests expose why a universal one-refund-per-order invariant is wrong. The runtime Java API/tool still accepts **full-order** refunds only; no production or live partial-refund support is claimed.

## Evidence

The workflow always uploads stage artifacts, including failures. `locked_experiment.json`, source snapshots, investigator decisions/proposals/traces, preflight, tool seeds, raw world logs/ledgers/events, model continuations, build/image hashes, isolation probes, per-plan outcomes, usage and measured wall time are retained. `evidence-hashes.json` hashes finalized outputs; it is consistency evidence, not external attestation. Dollar costs are not inferred.

Portable replay, independently supplied candidate commits, withheld variants, C0/C2/C4 comparisons and the demo remain subsequent work. No superiority or general bug-finding accuracy is established by G6.

## Failed attempts retained

- Initial code `417cef542dcb82ae9ab24fb42dc36ac9d8744e7c`, Actions [40880876546](https://github.com/PrasathJaga/codex-wheel/actions/runs/40880876546): broker negative test failed on an unexpected Host header. Genuine runtime step was skipped, so this run made no model calls. Correction `950bf1778816097781cccf7bc63c5d32f4942ef9` explicitly rejects non-gateway Host headers.
- Actions [40881024732](https://github.com/PrasathJaga/codex-wheel/actions/runs/40881024732) at `950bf1778816097781cccf7bc63c5d32f4942ef9`: offline tests passed, confinement probes passed, three JAR variants built, 15 genuine investigator responses and four genuine support-agent selections were recorded. Both benign investigators abstained; inherited stress-control origin was recorded. All 48 attempted worlds hit `KeyError` while looking up a published port on the internal-only network. Every plan was `analysis_error`; no runtime regression/repeatability was established. The artifact ZIP is `12899789316`, SHA-256 `62b09cbe418c47b84b315562fa0798a907170fc32cf44e0acb0adf1a2f80a3dd`; inspected response models were `muse-spark-1.3`, with 56,079 investigator tokens and 3,278 support-agent tokens. These are provider-reported tokens, not dollar costs.
- Correction `367626239f7acc703e9e0c693117a0c8718377e9` uses direct internal bridge addresses with no published producer ports, cleans up failed starts immediately, adds a regression test for missing published-port mappings, and adds sanitized stage/world progress output. This preserves outbound isolation. Earlier failed runs are not relabeled as successful evidence.


## Verified execution at 367626239f7acc703e9e0c693117a0c8718377e9

Actions [40881599825](https://github.com/PrasathJaga/codex-wheel/actions/runs/40881599825) passed. Inspected artifact [12901497160](https://github.com/PrasathJaga/codex-wheel/actions/runs/40881599825/artifacts/12901497160) contains 48 completed worlds, 18 genuine investigator calls and 52 genuine support-agent calls, all identifying `muse-spark-1.3`. Those 52 calls are four initial selections plus 48 post-tool continuations. Provider-reported usage: 76,657 investigator tokens and 47,677 support-agent tokens. Measured run wall time: approximately 747.4 seconds. No dollar cost is inferred.

| Experiment | Baseline effects across 3 trials | Candidate effects across 3 trials | Verdict |
| --- | --- | --- | --- |
| M1 selected: 2500, downstream drop | 1 / 1 / 1 | 2 / 2 / 2 | reproduced_regression |
| M2 selected: 7500, downstream 502 | 1 / 1 / 1 | 2 / 2 / 2 | reproduced_regression |
| B1 inherited stress: downstream drop | 1 / 1 / 1 | 1 / 1 / 1 | not_reproduced |
| B2 inherited stress: downstream 502 | 1 / 1 / 1 | 1 / 1 / 1 | not_reproduced |
| M1/M2/B1/B2 no-fault controls (4 plans) | 1 / 1 / 1 each | 1 / 1 / 1 each | not_reproduced each |

Both benign investigators explicitly abstained. Their stress controls inherited the corresponding breaking-case plan under the predeclared protocol; these are not independently proposed benign experiments. M1 candidate retries retained the same hashed key in all three trials; M2 candidate 502 retries used two distinct hashed keys in all three trials. All worlds verified fresh empty state, post-commit gateway observations, disk/HTTP ledger agreement, peer/source/image parity and graceful restart recovery. Every world has a genuine final support-agent message. All ten confinement probes passed and 194 mandatory integrity checkpoints were recorded.

Independent artifact inspection recomputed the ZIP and locked-plan digests, every listed finalized evidence-file hash, selected source hashes, paired trial inventory, unchanged peer hashes and persisted ledger row counts. The evidence provides bounded repeatability under these frozen plans; it does not measure independent investigator resampling reliability.

- ZIP SHA-256: `5e5db684b91f7298cc72c08f63efdeaf1f970d9aa671e6c19030f91b113035e4`.
- Locked plan SHA-256: `e4069cc7e2b3de850535c77c84bb7c7de4a280116f0a0d1ed86ed2840e5d1dd6`.
- G6 offline Actions tests: 46 passed, 1 live-only skip, 14 subtests passed. The broker test executed and passed.
- Code-revision full regression: PR workflow [40881611211](https://github.com/PrasathJaga/codex-wheel/actions/runs/40881611211) and push workflow [40881599583](https://github.com/PrasathJaga/codex-wheel/actions/runs/40881599583) passed, including Java unit/domain smoke, Python wrapper, live Java/Python integration and the existing 48-world manual matrix.

This is a verified G6 repeatability/control/container slice. Full adversarial evaluator protection and live partial-refund support remain incomplete. Portable replay and fair C0/C2/C4 evaluation are next; PR #8 must be merged before treating this as master functionality.
