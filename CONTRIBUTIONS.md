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
