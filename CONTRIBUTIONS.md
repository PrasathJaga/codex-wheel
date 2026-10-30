# Codex Wheel — Hackathon contribution and provenance ledger

Building window in the supplied Participant Guide: October 27–November 4, 2026. Track: Indie Developer. Theme: Push the Frontier.

## Pre-existing work

The separate codecx-wheel-main.zip contains earlier analysis/indexing utilities. That archive has not been copied into this repository. Architecture documents are design sources, not implementation evidence. Only event-period functionality may be highlighted as newly built in the demo.

## Event-period implementation and evidence

| Work | Implementation commit | Observed evidence |
| --- | --- | --- |
| G0/G1 synthetic Java API, Python wrapper, initial tests | 053a0c474fd24e81f39e626fe778a65f66b91016; master merge 07905405028fa244c5ca3ed82462bae00add4e43 | Actions 40855794807 passed; this baseline did not execute the live integration test |
| G1 live Java/Python HTTP and credential-protected evaluator reads | 4b912e0574013d743d6c5921288e143f44085e9d; master merge 185008c76ee75905b8965d9067f339e645e5c03d | Actions 40856908942: all jobs passed, one live test passed without skipping |
| G2/G3 manual buffered faults, append ledger, M1/M2 and controls | 875d67ab69beaeeef925442a1c1212487322ff01 and 34b5c685a77790a0df013ab44a059cf613edb39b | Actions 40857277640 passed; 48 worlds; artifact 12889463709 |
| G2 merge into integration branch | ab1eb8e241f45c5c02195fb2f986aee042a4e718 | PR #3 targeted hackathon/g1-live-integration, not master; corrective PR is required |

These are AI-assisted event-period contributions. Git history and linked execution evidence establish the boundary; the old archive and design history are not claimed as newly implemented.

## Claim ledger

| Feature | Status | Scope and limits |
| --- | --- | --- |
| Public repository | verified through GitHub metadata | PrasathJaga/codex-wheel |
| G1 live synthetic API/wrapper | verified_with_run | HTTP credential boundary; no hostile-code isolation |
| G2 buffered success then drop/502 | verified_with_run for manual fixtures | First persisted effect observed before downstream fault |
| G3 seeded M1/M2 manual comparisons | verified_with_run | Three trials, 1 baseline vs 2 candidate effects under relevant fault |
| Benign/no-fault controls and restart recovery | verified_with_run on disclosed matrix | One effect in all such worlds; graceful restart, not power-loss guarantee |
| Genuine Meta support agent and investigator | planned | Model calls: zero; no live model evidence |
| Full G6/G7 protection/replay/evaluation | incomplete | Hashes and repeated trials exist; full isolation, tamper rejection, replay and fair competitor evaluation remain outstanding |
| Demo video and final submission | planned | No completed or submitted demo is claimed |

## Evidence bundle

Run: https://github.com/PrasathJaga/codex-wheel/actions/runs/40857277640

Artifact: https://github.com/PrasathJaga/codex-wheel/actions/runs/40857277640/artifacts/12889463709

ZIP SHA-256: 0559c422e59f1f55dac5ae61ee7b31a1b7d69a5ce00820fd7cd9f03bbca99a89

Frozen plan SHA-256: 12fc464f9fd053360f6c8a15166ebc81bec3201bafc6b94b502a11ea87f6109d

Artifact inspection confirmed 48 worlds, actual RemoteProtocolError on drops, same-key retry except M2 candidate 502, and ledger recovery. No model discovery, generalization or superiority is inferred.

## Third-party dependencies and rights

Java, Spring Boot, Python, httpx, pytest and GitHub Actions are used under their upstream terms. Fixtures are synthetic. Rights/license review remains a submission responsibility; use of these dependencies is not a blanket legal clearance. Do not add employer code, real payments/customer data, or credentials.

## Remaining competition requirements

Meaningful genuine Meta model use is still unfulfilled. A public accessible three-minute demo highlighting only event-period work, submission details/contributors, and final rights/provenance review are still pending. The supplied Guide sets November 4, 2026 at 9 PM EST (November 5 at 7:30 AM IST) as the submission deadline. Organizer decisions control eligibility; this ledger is not a certification.

Architecture obligations not yet satisfied include OS-level evaluator separation, constrained execution/model gateway, robust plan freeze and tamper rejection, legitimate partial-refund counterexamples and fair baseline comparisons. Do not label these complete.

## G4 branch contribution (2026-10-29)

Added a credential-owning Meta support-agent gateway, strict intent validation, frozen conversation replay, credential-free wrapper subprocesses, bounded live workflow and negative contract tests. Status: implemented, live verification pending. This supersedes the earlier planned-only support-agent status for this branch, but does not claim completed G4/G5 gates. PR #4 is now merged to master at c04543143fd78840c8f76af8ad0974ff009c5175; master Actions 40865513972 passed.

G4 execution update: commit c295b9d27072ee207cb5cf61cb52ad01efd24526, Actions 40868779979, inspected artifact 12894409373 verifies six genuine muse-spark-1.3 calls and four worlds: one effect in each baseline, two in each faulty candidate, with the model reporting refund success. The previous zero-model-call statements apply to the earlier manual matrix, not this new slice. Meaningful runtime Meta integration is now demonstrated for these synthetic cases; full G4 preflight, G5 investigator and competition submission remain incomplete. See docs/G4_META_RUNTIME.md for failed-attempt disclosure and exact hashes.

## Preflight/freeze branch contribution (2026-10-29)

Added side-effect-free mock tool dispatch after genuine support-agent selection, all-or-nothing preflight acceptance, mandatory file/hash checks before execution and final publication, stale-output rejection and negative-path tests. Implementation exists; this branch's live execution is pending. PR #5 merged as 5b14f7309f0aaf78ce41ff9fb892e11ec5a87a23; master Actions 40870468023 passed. See docs/PREFLIGHT_FREEZE_GATES.md for precise architecture mapping and remaining limits.

Preflight/freeze execution update: commit 91f63a37640d68e302ad0b385d0c8662e71ce318, live Actions 40872383954 and inspected artifact 12895724593 verify two mock preflights selected by genuine Meta calls, six real generations, four expected ledger worlds and 18 integrity checkpoints. See docs/PREFLIGHT_FREEZE_GATES.md for hashes, separate negative-path test evidence and remaining limits. No G5 investigator or comparative superiority is claimed.

## G5 investigator branch contribution (2026-10-29)

Implemented a bounded genuine Meta investigator loop with read-only in-memory source/diff mediation, exact source-reference validation, generated customer/amount/fault proposals, abstention and bounded rejection handling. Runner consumes accepted proposals before preflight/freeze and reports actual one-trial outcomes without forcing a regression. Local fake-client tests pass; live verification is pending. G5_INVESTIGATOR.md discloses seeded-source scope and outstanding evaluation/isolation work.

G5 execution update: code commit 7efa2daa2bb9e8b65d1948c2ad051fbd29bf0efb, Actions 40874813904, inspected artifact 12898145845 verifies eight genuine investigator calls plus six support-agent calls. Generated fault plans produced one baseline effect versus two candidate effects for both cases. Two incorrect citations were rejected and corrected before execution. M2 amount 7500 was constrained by the documented public fixture, not autonomously discovered. The earlier low-value M2 run is retained as a design-conformance deviation. See docs/G5_INVESTIGATOR.md for hashes and exact limits.


## G6 repeatability branch contribution (2026-10-29)

Added a separate constrained Docker runner, no-network wrapper with a narrow Unix-socket refund broker, internal-network producer, confinement probes, frozen peer/source/image/JAR/policy/fixture checks, three paired trials per accepted plan, benign investigations and predeclared abstention stress controls, no-fault controls, conservative signature-based verdict aggregation, explicit model request limits and offline operation-scope counterexamples. Earlier G5 and master CI evidence remains historical; G6 runtime verification is pending until its own Actions artifacts are inspected. See docs/G6_REPEATABILITY.md. This is AI-assisted event-period work; no pre-event implementation was imported.


G6 execution update: code 367626239f7acc703e9e0c693117a0c8718377e9, Actions 40881599825, artifact 12901497160 independently inspected: 48 completed worlds, 18 investigator calls, 52 support-agent calls, three paired trials per frozen plan, M1/M2 baseline 1 versus candidate 2 effects in every selected trial, and all benign/no-fault controls one effect. Both benign investigators abstained; inherited stress-control origin is disclosed. Ten confinement probes and 194 integrity checkpoints were recorded. PR/push regression runs 40881611211 and 40881599583 passed. Initial broker and internal-network setup failures are retained in docs/G6_REPEATABILITY.md, alongside exact hashes, provider usage and limits. This establishes a bounded G6 slice, not blind discovery, independent investigator repeatability, a general hostile-code guarantee, live partial-refund support or baseline superiority. PR #8 is open, not merged.


## Portable replay and reviewed pinned intake (2026-10-30)

Added explicit full-SHA intake with unchanged-peer/build checks and exact reviewed source-byte admission; portable replay packaging with source Git bundle, original G6 evidence, archived runtime images and JARs; independent expected manifest hash, pre-execution verification and clean-runner deterministic replay. Default replay uses zero new model calls and never labels recorded messages as fresh inference. Optional post-tool continuations are explicit and bounded. Synthetic pinned commits are disclosed and are not external developer changes or withheld cases. Runtime verification is pending. See docs/REPLAY_AND_INTAKE.md for reconstruction limits, source scope, trust assumptions and evidence status. This continues the original plan; no conditional stretch implementation is activated.


Replay execution update: code d9801353f28df4a35d8d56e4ed9757628e6f45b1, Actions 40974431811, inspected bundle 12942032169 and replay evidence 12941334841 verify caller-supplied reviewed pinned source pairs and 48 completed fresh-state worlds on a separate runner. Both selected defects reproduced across three pairs and all benign/no-fault controls retained one effect. Replay used zero new investigator/support-agent calls; genuine Meta analysis usage remains independently evidenced in G6 (70 calls in run 40881599825). 61 offline tests plus 14 subtests passed, with one live-only skip; code-revision full regressions 40974436568 and 40974431820 passed. The earlier generated-pin replay run 40973653126 also passed and is reported separately. Source/JAR/image/manifest hashes, reconstruction limits and actual outcomes are in docs/REPLAY_AND_INTAKE.md. PR #9 merged as de85302d434c8e4ba45f7d3de8d9d3a08098f907; no full G7 evaluation/demo/submission or conditional stretch completion is claimed.
