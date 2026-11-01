# Registered generic Meta integration v1 — 2 November 2026

## Purpose and fixed process

The next gate after PR54's unpaid generic orchestration controls is a real paid
integration validation. No investigator prompt, source admission, plan schema,
executor, expectation checker, citation resolver, retry policy or repair process
is changed. All 23 trusted preflight modules are bound by the registered
`implementation_sha256`, corresponding to master
`08672d7bc92edfa3a74cec0a4c2f1bebe501af8a`.

The public control artifacts from run 41344873422, artifact 13098299107, ZIP SHA256
`98644b64fe6bad2dd99f0a64037a057d1e7e2e57458b1bbeae84cf6413fab508`,
were downloaded and digest-verified. Their image RepoDigests are reused exactly,
not resolved again from mutable tags. Those controls previously passed with model
test doubles, not real Meta responses.

This registration uses known internally authored Python/Java HTTP controls. Both
languages have one preserving and one violating pair. They are deliberately tiny:
the declared `/value` expectation is integer 4; violating candidates return 5.
Existing checks are syntax/runtime checks, not claimed well-written JUnit suites.
There is one declared operation. Success would establish schema/provider/runtime
integration under these conditions, not interesting adversarial search, unfamiliar
transfer, conventional-baseline superiority, external adoption, or general repair.

The source generator reuses `http_experiment_smoke.exercise` to capture input data
without execution. Its synthetic empty-world return is only a capture mechanism;
it is not recorded as live execution evidence. The old supplied control plan is
discarded. Committed case packets contain source archives, configuration, interface,
expectations and investigation policy; no distinguishing plan or repair answer is
passed to the model. The source behavior and expectation intentionally make the
integration task easy. Do not present it as a blind discovery benchmark.

## Registration and budget

`evaluation/generic_paid_integration_v1/registration.json` commits case digests,
implementation, order, image digests, provenance and expectations commitment.
`expectations.json` records already-known control verdicts separately from model
inputs. No input may change after launch to achieve a favorable result.

Fixed order: Python preserving, Python violating, Java preserving, Java violating.
Each uses the unchanged generic investigator: lifecycle prerequisites, one
selection request, strict admission/frozen experiment, two paired trials, then one
evidence-referenced diagnosis when eligible. Maximum **eight model requests**,
aggregate **80,000 completion tokens** (12,000 selection + 8,000 diagnosis per
case). Standard `muse-spark-1.3`, provider retries disabled. No repair requests or
second selection after feedback. A rejected proposal, abstention or inconclusive
result remains recorded; it does not trigger correction. Infrastructure, access,
provider or invalid-baseline failures stop remaining cases.

Reported usage and the existing receipt pricing basis produce token-cost estimates;
missing usage stays unknown. Estimates are not verified invoices or remaining
credit balances. No call is made merely to spend credits. This finite paid work is
covered by the user's existing paid-call authorization.

## Launch and privacy boundary

PR events validate registrations with no Docker, SDK, key or inference. The trusted
paid job runs only on `evaluation/generic-meta-integration-v1-once`, run attempt 1.
Concurrency serialization and a fail-closed prior-launch history check reject
subsequent launches before accessing the model key. Cases are run once in registered
order; attempt claims and all raw receipts remain in the final artifact. The live
branch is created only from the tested committed PR head. No automatic paid master
workflow or ordinary-PR paid operation is introduced.

The trusted host checks out Wheel; external containers receive only authenticated
external control source and disposable runtime resources, never that checkout or
Meta/GitHub credentials. The launcher pops the model key immediately and constructs
the SDK only when the unchanged investigator reaches inference after prerequisites.
The executor's Docker environment, mount and network protections remain unchanged.
Selected external source is explicitly approved for this model integration; no
Wheel source is included in context.

The separate once-only branch history guard supplements the existing local claim
store. Claims are preserved even on failure. They do not provide a cross-provider
billing ledger, and deleting history/claims would defeat the bound. Do not reset
those guards or manually rerun this integration.

## Review every outcome

Inspect summary, original provider receipts, admission/abstention, baseline/candidate
HTTP evidence, diagnosis references, token usage and final verdicts. Source and
evidence reference validity alone does not prove a causal explanation correct.
The independent checker owns the verdict; diagnosis cannot overwrite it. Compare
against the separately committed known expectations, without altering either.

This PR registers and launches integration. Results are pending until the real run
and artifact audit complete. The earlier failed PetClinic paid pilot remains
unchanged counterevidence. The broader roadmap still requires credible unfamiliar
comparisons, independent preparation, route extraction and bounded repair.
