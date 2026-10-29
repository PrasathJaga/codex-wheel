# G6 repeatability and controls

Implementation branch: `hackathon/g6-repeatability-controls`, based on verified master `ec55072fede610c26265e9660828f9530cf1a4f6` (PR #7 merged; master run 40876333556 passed). This document records the implementation protocol; execution results must be added from inspected Actions evidence.

## Predeclared protocol

`python -m wheel.g6` requires Docker, Java 21/Maven, Python and a genuine `MODEL_API_KEY`. It refuses a dirty tracked checkout or workflow/revision mismatch. It checks container availability/confinement and builds copied Java variants before spending model credits. There is no fallback to host execution, manual breaking plans or fake inference.

A genuine Meta investigator separately reads M1/M2/B1/B2 sources and proposes experiments or abstains. Its total request budget is 24, with the existing six-turn limit per investigation and source/citation gates retained. Labels are not sent to the investigator. M2/B2 retain the disclosed high-value public eligibility constraint. These remain known seeded cases, not a blind benchmark.

An explicit benign abstention is preserved. The predeclared benign stress control then inherits the corresponding M1/M2 proposal **before any world executes**, with its origin recorded. It is never described as the benign investigator's accepted proposal. Budget exhaustion, invalid-proposal exhaustion and other model errors do not take that fallback. A breaking-case abstention stops the run and records its stage.

All four customer triggers undergo genuine support-agent selection and side-effect-free mocked-tool preflight. Seeds preserve provider-compatible history and tool-call IDs; generated retry keys remain inside the actual wrapper. Plans, sources, peer hashes, authorization fixtures, source evidence, oracle code, policy, immutable runtime image IDs, built JAR hashes and three-trial count are locked before differential execution.

Each selected plan and a corresponding no-fault control receive three fresh baseline/candidate pairs: up to 8 plans, 24 pairs, 48 worlds. Each world receives a new ledger, producer process, fault gateway, wrapper container and evaluator token; graceful restart is verified inside that world's state only. The support-agent budget is at most 52 requests: four initial selections plus one genuine continuation per world. Initial tool-selection variability is held fixed; this does not measure independent investigator or initial-agent resampling reliability.

All outcomes are retained. Stable 3/3 baseline-pass and 3/3 candidate-fail signatures are required for `reproduced_regression`. Mixed signatures/results are `inconclusive`; failed baselines cannot establish a regression. Missing/failed execution or continuation is explicit. Model wording and expected mutation labels never decide the verdict. Accepted pass-through or ineffective rules are allowed; they can return `not_reproduced`, which never means safe to merge.

## Isolation and its limits

The trusted host owns Docker orchestration, the Meta key, frozen evidence, oracle and fixture expectations. The Python wrapper runs non-root with no network, read-only root, dropped capabilities, no-new-privileges, CPU/memory/PID bounds and a bounded tmpfs. Its only mounts are the candidate Python file, trusted worker and a Unix broker socket. The broker permits only bounded `POST /refunds`, strips unrelated headers and forwards only to the fixed local gateway. It denies the evaluator route and arbitrary destinations. The Meta SDK/client is not mounted.

The Java producer runs in a separate constrained container on an internal Docker network. Only its JAR and its fresh state directory are mounted; the API is published on a loopback host port. The producer necessarily owns its synthetic ledger and evaluator token. The host independently compares ledger bytes to the protected HTTP snapshot and verifies commit-before-fault observations. Root filesystem, capability, privilege, network, environment and host-file-access probes run before paid calls. Actual image IDs are pinned for all worlds in that run; mutable image tags are resolved at setup, not silently reused across trials.

This materially strengthens isolation over same-host subprocess environment filtering. It is **not** a separate tamper-proof database, hostile-kernel isolation certification, hermetic build, power-loss guarantee or proof that malicious producer code cannot forge its own ledger. Builds execute trusted synthetic source on the host. Dependency ranges/image tags may resolve differently across runs; resolved images, dependency versions and JAR hashes are archived.

## Scope counterexamples

`check_operations` has offline counterexamples showing two authorized partial refunds on one order are legitimate when allocated to distinct authorization IDs. Duplicate, missing, misallocated and wrong-amount effects fail. These tests expose why a universal one-refund-per-order invariant is wrong. The runtime Java API/tool still accepts **full-order** refunds only; no production or live partial-refund support is claimed.

## Evidence

The workflow always uploads stage artifacts, including failures. `locked_experiment.json`, source snapshots, investigator decisions/proposals/traces, preflight, tool seeds, raw world logs/ledgers/events, model continuations, build/image hashes, isolation probes, per-plan outcomes, usage and measured wall time are retained. `evidence-hashes.json` hashes finalized outputs; it is consistency evidence, not external attestation. Dollar costs are not inferred.

Portable replay, independently supplied candidate commits, withheld variants, C0/C2/C4 comparisons and the demo remain subsequent work. No superiority or general bug-finding accuracy is established by G6.
