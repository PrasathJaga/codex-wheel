# Generic source-aware investigator orchestration v1

This connects the shared Java/Python HTTP interface to bounded model selection,
paired execution and evidence-linked diagnosis. It does not establish that Meta
successfully investigates unfamiliar projects. Runtime controls use explicit model
test doubles; a fresh registered paid evaluation remains a separate gate.
No original PetClinic case, prediction, prompt, receipt or outcome is changed.

## Common process and trust inputs

The same `preflight.generic_investigator` pipeline takes authenticated source
archives, source descriptor, execution manifest, trusted lifecycle policy, reviewed
HTTP interface, approved expectation contract, and a separate investigation policy.
Interfaces and expectations must be reviewed outside project/model output. Route
extraction and automatic business-expectation approval are not implemented.
Project adapters must not encode a defect, desired outcome, selected plan or repair.

The investigation policy has exactly these fields:

- `schema`: `wheel-generic-investigation-policy-v1`;
- `attempt_id`: a bounded identifier unique in the caller's persistent claim store;
- `implementation_sha256`: `implementation_sha256()` over all preflight Python
  modules, including fixed prompts and reused executor/validator/gateway code;
- `source_sha256`, `lifecycle_policy_sha256`, `interface_sha256`, `contract_sha256`:
  canonical commitments to the exact trusted inputs;
- `source_paths`: 1–32 explicit approved context files from admitted archives;
- `paid_execution_enabled`: boolean, false for unpaid controls.

This hash binding is not a signature or proof of independent review. Trusted
policy and claim storage must be controlled by the caller, never supplied as
self-approval by a project or the model. Persist claims across machines/runs when
using distributed execution. An ephemeral directory alone cannot enforce a global
budget. No automatic paid GitHub workflow is introduced by this PR.

The approved context contains numbered source from both sides, exact selected-file
diffs, interface, expectation contract and the complete closed plan JSON schema.
Added/deleted files remain visible through their one-sided source/diff. Changed
paths outside the approved scope are enumerated, not silently treated as examined.
Context over 180,000 serialized bytes is rejected rather than truncated. This is
explicit bounded source scope, not full repository understanding. No expected case
labels, conventional answers, reference repair or original supplied control plan
is provided. Sending selected source is an explicit operator-approved model action;
static preparation itself does not upload anything.

Before selection, lifecycle controls run baseline and candidate once. A failed
baseline or lifecycle error stops before model construction/inference. These are
health/build/test controls, not proof that the baseline satisfies every business
expectation. The baseline must separately pass the model-selected experiment.

## One bounded investigation

1. Validate source, manifest, lifecycle, interface, all operation expectations,
   implementation commitments and source scope before Docker or model requests.
2. Atomically claim the attempt with exclusive file creation, retaining it on
   every failure. Output directories are also single-use. No automatic rerun.
3. Execute the lifecycle prerequisites without model input.
4. Request one selection: strict `propose` with hypothesis, 2–6 baseline/candidate
   source citations and exact plan, or strict `abstain` with reason. The complete
   `plan_tool_schema` supplies required action fields and request-body bounds.
5. Reject unknown aliases, unsupported actions or unresolved citations. Retain
   the raw response and rejection/abstention. No correction request or resampling.
6. Trusted code validates and freezes the admitted plan with the already approved
   interface/contract/lifecycle. The model cannot approve configuration or tools.
7. Run two fresh paired trials through the existing executor/checker. Baseline
   expectation failure stops candidate execution. Existing failure, mixed-result
   and infrastructure classifications remain intact.
8. Only after a completed comparison, request one diagnosis with exact evidence
   IDs. Resolve 1–6 source citations and 1–16 execution references. Preserve a
   rejected/failed diagnosis without changing the checker verdict.

The fixed model is Standard `muse-spark-1.3`, using the existing Meta gateway:
selection ≤12,000 completion tokens, diagnosis ≤8,000, at most two requests,
300-second provider timeout, SDK retries disabled, request cap 262,144 bytes.
No request is made merely to consume tokens. Reused gateway receipts are written
before transmission and preserve raw provider responses, usage and failure states.
The model reasoning budget is not a spending invoice; actual usage/invoice totals
must be reported from real receipts/accounting in a paid evaluation.

The CLI defaults to **preparation only**, without SDK, key or execution:

```bash
python -m preflight.generic_investigator \
  --baseline base.tar.gz --candidate head.tar.gz --source source.json \
  --manifest manifest.json --lifecycle lifecycle-policy.json \
  --interface interface.json --contract expectations.json \
  --policy investigation-policy.json --output context-for-review.json
```

`--live --claims /path/to/persistent-trusted-claims` additionally requires a
paid-enabled reviewed policy and `MODEL_API_KEY`. The key is removed from the host
environment immediately and held only by the trusted SDK client, constructed after
lifecycle controls pass. External code receives neither project credentials nor
Wheel source. `--postgres` uses the existing Postgres lifecycle/independent snapshots;
HTTP expectations still do not grade persistence predicates. No model may submit
SQL, arbitrary URLs, shell commands, credentials or a repair.

## Meaning of the result

The independent verifier owns `confirmed_contract_violation`, `no_violation_observed`,
`baseline_invalid`, `inconclusive` and infrastructure/lifecycle outcomes. An invalid
proposal or abstention is inconclusive, not a successful investigation. A rejected
diagnosis does not erase a valid finding; an eloquent diagnosis cannot create one.
`business_behavior_verified` stays false: checking declared HTTP expectations is
bounded and does not establish persistence or universal business correctness.

Diagnostic evidence consists of original action identities, HTTP statuses,
response hashes, checker failures and at most 512 bytes of response excerpt per
action. Truncation is explicitly marked; complete original response bytes remain
in executor artifacts. Citation resolution proves references exist, not that a
proposed causal explanation is correct. The accepted diagnosis status explicitly
says `references_validated_not_independent_causal_proof`. Human/independent review
is still required before presenting causal or general capability claims.

Artifacts preserve the policy, exact selection input, original responses,
frozen admitted experiment, lifecycle and paired executor evidence, diagnosis
projection and final result. Paid/test-double transports and attempt counts are
separate. Model/transport failure cannot trigger another experiment.

## Validation and next gate

Unit checks cover exact schema delivery, source/diff scope, changed implementation,
invalid aliases/citations, paid-disabled execution, invalid-baseline zero spending,
single-use claims, rejection, abstention, diagnosis rejection and checker authority.
The dedicated CI runs real Java/Python preserving and violating HTTP services with
explicit test-double provider receipts through the same generic pipeline. These
are authored orchestration controls, not paid Meta results or transfer evaluation.

Next: freeze this process and register a bounded real paid integration validation,
with all inputs/budgets committed before execution and every outcome retained.
Known authored controls are development/integration evidence, not unfamiliar
benchmark discoveries. A separate unfamiliar evaluation still needs credible
conventional comparison and independent preparation. Repair and automatic route
extraction remain later capabilities; neither is hidden in these adapters.
