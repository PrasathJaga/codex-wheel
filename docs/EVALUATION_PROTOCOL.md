# Step 1 — Evaluation protocol v1

This defines the comparison before new runs. It does not execute C0/C2/C4, call Meta, create a withheld result, or activate the conditional stretch plan. Machine-readable policy: `evaluation/protocol_v1.json`; exact-byte SHA-256: `911e8a5dca874967b52fd313e6f4e975f9813fe8b3f7f2750e0392f6538ef364`.

Adoption means merging this protocol and pinning that independently trusted hash in the future evaluation run. A sidecar cannot authorize changed content. Amendments require a new version and reason before new execution; retain old protocols/results. Source base: master `e8ee44da1788a6ad2a14f1fcbf575e54a843a080` (PR #10 merged). No new evaluation result is asserted here.

## Methods

| Method | Fixed before execution | Permitted evidence |
| --- | --- | --- |
| C0 | Deterministic read-only public API/tool contract extraction from each pinned revision | Schema changed/unchanged, unsupported extraction or error; no business-safety verdict from schema alone |
| C2 | Complete fixed Cartesian suite over every permitted public amount and all three actions: pass-through, post-commit drop and post-commit 502 | Actual protected-ledger results, with no source/diff-conditioned test selection |
| C4 | One fresh bounded Meta source investigation per case; at most one selected plan and one separate no-fault control | Source-grounded proposal, genuine trigger preflight and actual effects/verdict, or explicit abstention/failure |
| C3 | Optional, not implemented/evaluated in v1 | `not_evaluated`, never a hypothetical zero score |

C2 is a competent full suite over this small vocabulary, rather than a deliberately brittle single template. It can tie or outperform C4. Its rules/payloads are fixed before new comparative outcomes and cannot use diffs or hidden labels to choose a test. Report actual breadth and cost differences; this is not an equal-budget comparison.

C0 must derive/validate the supported public surface from actual pinned source: POST /refunds, required header, request fields/types, committed-response fields and the issue_refund tool schema. Unsupported extraction must remain unsupported; returning a constant “unchanged” is not an implementation. No working OpenAPI/schema comparator is claimed in this planning step. The extractor belongs to Step 2.

C4 uses genuine Meta `muse-spark-1.3` through `https://api.meta.ai/v1`. Its source tools and generation parameters are pinned. It must perform new inference after protocol adoption; saved G6 plans or replay messages cannot become fresh C4 selections. Accepted proposals require real source citations and a genuine support-agent selection/mock preflight. No oracle, prior outcomes, C0/C2 results, labels or secrets enter investigator context.

## Cases and source provenance

Core v1 contains the disclosed synthetic M1/M2/B1/B2 cases. Commit pairs, unchanged peers and source hashes are pinned to replay run 40974431811, artifact 12942032169, manifest root `614c53b29dbc03640d261dca94dce5414bcc9105f59f93b61a99207bcc01ede9`. The guard checks their provenance against the protected REPLAY_EVIDENCE_INDEX.json.

Java-side cases permit public amounts 2500 and 7500. Python-side cases retain the existing disclosed high-value eligibility of 7500. Both methods receive the same eligible amounts. Fixtures authorize one synthetic USD full-order operation. Evaluator labels are protected scoring data, not model context; `selection_inputs` exports only public fixture/source metadata without case labels or old results.

Designers have already seen these mechanisms and prior results. This is retrospective known-case design with a prospective lock for new runs, not a blind benchmark or generalization result. The existing B2 source also contains a benign annotation; preserve its exact bytes and disclose that public hint. The model-context restriction concerns evaluator-only labels and result feeds, not a claim that the public source is free of explanatory comments.

## Execution order and lock

1. Validate the protocol hash, protected components and source inventory. Pin the actual Step 2 evaluator/extractor/method implementation revision before running comparisons; those implementations do not exist merely because the design is frozen.
2. Expand the fixed C2 suite and perform the fresh C4 investigations and genuine mocked-tool trigger preflights. Freeze every method's plans/seeds **before any comparative world starts**, so earlier C2 outcomes cannot influence C4 selection.
3. Execute/report in C0, C2, C4 order using the fixed case order. Each executed plan has three fresh baseline/candidate pairs and matching peer, fixture, tool/prompt/model policy, oracle and runtime versions. Initial dialogue/seed may differ between methods; business arguments must match authorization. Within every pair, replay the exact same accepted seed.
4. Preserve all attempts and outcomes. No post-outcome replanning, manual fallback, extra investigator resampling or reuse of old verdicts as fresh results. Model prose never determines correctness.

## Workload and genuine model calls

Each plan has three fresh paired executions. Only trial index 0 gets a genuine post-tool continuation for both worlds. Trials 1–2 are deterministic tool/backend repeats with null model replies. Missing representative responses stay unavailable/error; do not select a nicer later trial or copy recorded text. This differs from G6's 48 genuine continuations and must be labeled in reports and the demo.

| Method | Maximum plans | Maximum worlds | Initial support requests | Representative continuations | Investigator requests |
| --- | ---: | ---: | ---: | ---: | ---: |
| C0 | 0 runtime plans | 0 | 0 | 0 | 0 |
| C2 | 18 | 108 | 6 | 36 | 0 |
| C4 | 8 | 48 | 4 | 16 | 24 |
| **Core maximum** | **26** | **156** | **10** | **52** | **24** |

Core v1 caps new request attempts at **86**: 62 support plus 24 investigator. Failed requests consume budget; provider retries are disabled. Support output is capped at 1024 tokens/request, investigator output at 2048; combined configured output capacity is 112,640 tokens. Request messages are bounded to 100,000 characters before transmission. These are planned maxima, not measured usage/cost. Record provider-reported usage where available; pricing, remaining credits and USD cost are unknown, not fabricated.

C2 has six plans per Java case and three per Python case. One genuine support preflight per case/amount is reused across its rules. A failed amount preflight marks those plans trigger_not_reached; other predeclared amounts may continue without altering the suite.

C4 has one initial investigation per case, up to six turns, three rejected proposals and four tool calls per turn. One accepted plan may get one separately labeled no-fault control with the same amount/seed. If the selected rule itself is pass-through, report the semantic duplication; the control is not another discovery.

C4 abstention remains `abstained`: no primary worlds and no inherited C2/G6 plan. A failed C4 trigger stops the case before execution. G6's historical inherited benign stress controls cannot become fresh C4-selected successes. Actual workload can be below the caps after abstention/failure.

## Fairness and outcome accounting

C2 tests 18 fixed plans; C4 selects at most four experiments plus four diagnostic controls. Publish actual plans/worlds, selection attempts, request attempts/responses, tokens, setup and runtime. Do not claim equal-budget superiority or production reliability from four cases. Report ties/losses without weakening the baseline or changing the case inventory after outcomes.

A plan confirms regression only with valid integrity/parity, a verified intervention/causal chain and stable 3/3 baseline-pass/candidate-fail signatures. Mixed behavior or failed baseline invariants are inconclusive; infrastructure/hash/policy errors are analysis errors. No model narrative can modify the fixed oracle.

A case is flagged if at least one valid plan reproduces regression; preserve all its other failed/error attempts. With no confirmed plan, retain error/inconclusive/trigger-failure precedence rather than hiding failures behind a passing control. Abstentions remain abstentions. Not reproduced is limited to tested conditions and never means safe to merge. C0 uses its separate schema outcome namespace.

Report all twelve core case/method rows, all plan/trial outcomes and rejected/abstained/failed attempts. Publish raw breaking-case findings out of two, benign flags out of two, runtime coverage and abstention/error counts out of four, plus requests/usage/time. Zero findings after abstention is not a verified true negative. Missing/unperformed fields are null/not_evaluated, not invented performance zeros.

## Withheld case and deferred work

U1 remains not_evaluated and outside v1's budget. Admit it through a separate reviewed versioned case/source/budget lock before new execution, retaining the same C2 algorithm/C4 policy and unchanged oracle. Prefer an independent human evaluator; if unavailable, disclose authorship and call it investigator-withheld synthetic. Do not claim independent evaluation or assume agent delegation. If infeasible, report that honestly.

This does not activate the conditional stretch plan, new domains, arbitrary repository execution, live partial refunds or adversarial security claims.

## Offline guard and CI policy

`python -m wheel.evaluation_protocol --protocol evaluation/protocol_v1.json --expected-sha256 TRUSTED_EXPECTED_HASH` validates the design/source pins and expands workload counts. It imports no provider client and executes no comparison. Step 2 must integrate the guard with a trusted expected root before builds, inference or worlds, and lock its actual implementation revision.

Tests cover weakened C2 suites, extra C4 sampling, inherited abstention fallbacks, old-result reuse, budget/fixture/source/oracle drift and sidecar reauthorization. They are offline policy checks, not evaluation results.

Baseline verification now triggers on PRs targeting master, pushes to master and manual dispatch. Feature-branch pushes no longer schedule the full baseline suite alongside their PR check. Existing bounded Meta/replay workflow triggers are unchanged; no additional paid experiment is authorized or started by this PR. Post-merge verification remains separate from pre-merge integration checks.
