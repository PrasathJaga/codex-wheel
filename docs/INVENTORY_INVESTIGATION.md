# Bounded inventory investigation v1

This adapter investigates the known expiry-grace mutation in fixture PR #34. Existing unchanged JUnit already caught it (18 tests, 5 assertion failures and 1 error). The purpose is a source-aware investigation/execution integration in a second domain, not extra coverage beyond JUnit, AI necessity, independent transfer or blind discovery. Never merge PR #34.

## Registered limits

`evaluation/inventory_investigation_v1.json` pins both source revisions. Exact baseline file hashes and the one allowed candidate hash come from the previously merged candidate registration. Any other changed path or byte is unsupported. The protected unchanged client, oracle, tests, policy and implementation are bound before execution.

The trusted parent gives Meta complete numbered Java base/candidate source, unchanged Python client source and the actual diff. It supplies the declared business contract and action schema, not a target sequence, prior failed tests/logs or runtime outcomes. One Muse Spark 1.3 request, up to 6000 completion tokens, low reasoning effort, no SDK retries or feedback loop. Prompt+completion usage is recorded separately from this completion ceiling; dollar cost is unknown without billing information.

The response may abstain or propose 2–8 actions: RESERVE, TRIGGER_EXPIRY, CHECKOUT, RELEASE for buyer A/B, with fixed per-buyer reservation/order IDs. Actual reserve must precede use in the proposed syntax; a rejected reserve may still lead to a recorded 404. Exact inclusive source citations must resolve to candidate Java and BASE Python bytes. Invalid responses are retained and stop selection. There is no fallback sequence.

## Execution and oracle

Fresh unchanged Java tests run against both revisions and logs/exit codes are retained. Baseline test failure stops execution. Candidate catches remain recorded failures; a later `-DskipTests package` exists solely to observe the known defective candidate, not to approve its merge or pretend tests passed. No source/test/oracle safety checks are removed.

The registered happy-path control executes three baseline/candidate pairs before inference. If it fails, no paid request occurs. An admitted Meta sequence freezes before its six worlds: three baseline/candidate pairs with fresh state. Total ceiling is twelve worlds. A new Java container owns each world's local snapshot and evaluator token.

The producer reuses DockerRuntime image pinning, internal networking, non-root user, read-only root, dropped capabilities, no-new-privileges, PID/memory/CPU limits and confinement probes. It receives only its reviewed JAR, writable local state and its own evaluator token. The unchanged Python client executes in the trusted host harness with proxies disabled; it is not placed in the refund Unix-broker worker. Do not claim identical worker confinement or arbitrary hostile-source execution support.

The host records each DSL action and actual response/rejection, reads protected evaluator state, and reconciles it with the committed JSON file. The independent verifier reconstructs lifecycle history, checks stock conservation, matches stored orders to allocations and accepted receipts, and rejects confirmation after expiry/release. HTTP 500 is an execution error, not automatically an oversell. Baseline failure invalidates the comparison. Three passing baselines and three candidate contract violations establish reproduction only under the selected sequence.

Expiry remains an explicit semantic event, not elapsed wall-clock time or proof of a distributed in-flight race. The candidate may produce an invalid lifecycle with only one order; report that actual consequence rather than inventing two orders. This phase has no repair or financial calculator.

## Receipts and operation

Ordinary PR events run adapter unit tests, not paid inference. The live run is restricted to a dedicated named push branch and uses the existing MODEL_API_KEY secret. Do not push that branch casually or rerun for a favorable selection. Missing access, invalid baseline, failed confinement, rejected response and budget exhaustion are stop conditions.

Artifacts preserve source snapshots, implementation/policy lock, actual Java test logs, image identities, confinement checks, request/response/usage, proposal, per-action trace, on-disk states, selected/control world records, integrity checkpoints and summary. A small escaped static HTML index links conceptually to these adjacent records; it is not a hosted live dashboard or recorded agent conversation.

Any new attempt must have a separately versioned policy and retain this attempt. No automatic PR comments, repair commits or merges are performed by this adapter.
