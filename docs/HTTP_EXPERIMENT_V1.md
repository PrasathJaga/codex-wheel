# Shared bounded HTTP experiments and declared expectations

This extends the generic Java/Python service runner beyond lifecycle checks.
The same strict experiment format executes against both revisions and a trusted,
independent checker compares recorded HTTP status/JSON with declared expectations.
It does not yet connect Meta, extract routes automatically, diagnose a cause,
verify persistence predicates, propose repairs or establish unfamiliar transfer.
The original negative PetClinic pilot remains unchanged.

## Inputs, approval and freeze

The optional `--experiment` argument to `preflight.service_executor` accepts a
JSON bundle with exactly `interface`, `contract`, `plan`, `policy`. The runner
reconstructs source identities from authenticated archives and performs existing
manifest/lifecycle admission first. Experiment admission occurs before Docker.

The separate trusted experiment policy has schema `wheel-http-experiment-policy-v1`
and commits `lifecycle_policy_sha256`, `interface_sha256`, `contract_sha256`,
`plan_sha256`. It freezes exact admitted inputs; it is not a signature or proof
of operator approval. Policy and approved interface/expectations must originate
outside the external project or model response. A project must not approve itself.
Future Meta selection may propose a plan within those tools; trusted code must
validate and freeze that proposal, not accept arbitrary configuration from it.

The interface schema is `wheel-http-interface-v1`, binds `manifest_sha256`, and
contains 1–16 `operations`. Every operation has exactly `id`, `method`, `path`,
`body_schema`, `source_refs`:

- IDs are bounded identifiers. Methods are GET/POST/PUT/PATCH/DELETE.
- Paths are fixed internal routes, up to 200 characters, with letters/digits,
  slash, underscore and hyphen. No URLs, query strings, interpolation, arbitrary
  headers, authorization fields, redirects or external destinations are accepted.
- GET has no body. Other operations use null or a closed object schema, with up
  to 16 named scalar properties. Strings have minLength/maxLength (maximum 256),
  integers have minimum/maximum (within ±1,000,000), booleans have type only.
  `required` is explicit and `additionalProperties` must be false. Nested bodies,
  floats, regexes, uploads, authentication and conditional contracts need future
  reviewed capabilities; they are not silently approximated.
- 2–6 source references cover both revisions. Each has `side`, `path`,
  `line_start`, `line_end`, resolves to admitted UTF-8 source, and spans at most
  eight lines. Bounds resolution does not prove that the cited code implements
  the route; source/interface review is still required.

`tool_schema(interface, contract)` produces the complete closed JSON schema for
one plan, including each operation's exact action/body fields, constants, bounds
and maximum action count. This is the generic interface correction suggested by
the failed pilot. The v2 responses are not normalized or retrospectively accepted.

A plan has exactly:

```json
{
  "schema": "wheel-http-experiment-v1",
  "interface_sha256": "<canonical interface digest>",
  "contract_sha256": "<canonical contract digest>",
  "actions": [{"operation": "read_value", "body": null}]
}
```

Placeholders require real digests. There are 1–8 actions. Each has only `operation`
and `body`. Unknown aliases such as `op`, `ref`, `reference` or arbitrary `url`
are rejected rather than repaired after a model response.

## Business expectations are explicit inputs

The contract schema is `wheel-http-contract-v1`, binds `manifest_sha256`, and has
`provenance` plus 1–16 `checks`. Provenance has `kind` (`developer_declared` or
`reviewed_existing_contract`) and an attributable `reference`. These strings alone
do not establish approval; trusted policy review must verify the expectation.
The system does not invent a business rule from source or assume every baseline
response is correct. Intended changes need approved expectations that account for
the new requirement; disagreement with an old response is not automatically a bug.

Each check has `operation`, `statuses` (1–8 allowed HTTP statuses), `json_equals`
(0–8 assertions). Each assertion has `path` (1–8 string keys/nonnegative array
indices) and scalar `value` (string/integer/boolean/null). Equality is type-strict:
true is not 1, and missing is not null. Every selected operation needs a check.
Expectations apply uniformly across that operation's approved request domain;
conditional status/response rules are not supported in v1.

These are HTTP expectations only. Existing Postgres snapshots can still record
state before/after the experiment and after shutdown when the Postgres mode is
used, but this increment does not grade rows or infer financial impact. A response
contract cannot establish persisted business correctness by itself.

## Execution and result semantics

Both revisions use the exact same frozen plan. Each fresh world runs unchanged
configured checks and service startup first. Experiments only run after health
passes, against the private network IP revalidated by the runner. Requests use a
trusted HTTP worker with no proxy, cookies, credentials or redirect following.
Each action has a hard five-second maximum within a 60-second experiment budget
and the existing world/run budget. Worker teardown has its own bounded cleanup.
Responses are capped at 64 KiB; original bytes are retained as Base64 with length
and SHA256, including non-JSON/error responses. Action, response, deterministic
assertion failures and plan/evidence hashes remain in per-world evidence.

A timeout, oversized response, worker failure or transport error is an execution
error, not a business violation. Prior action evidence remains recorded. Unexpected
HTTP status or a required JSON mismatch/invalid body is a contract violation.
The checker uses the declared rule and actual response, never a model diagnosis.
With Postgres, `initial`, `after_health`, `after_experiment`, `after_stop` retain
separate meanings; missing later snapshots on failure are not invented.

A baseline expectation failure stops dependent candidate execution and reports
`baseline_invalid`. If lifecycle succeeds and all candidate worlds pass, the result
is `no_violation_observed`. All candidate worlds violating across at least two
fresh paired repetitions produce `confirmed_contract_violation`; a single trial
is only `observed_contract_violation`. Mixed passing/violating repetitions produce
`inconclusive`. Startup/infrastructure failures retain their existing classifications.
The CLI exits nonzero for a finding or adverse result. Authored smoke workflows
assert expected failure outcomes explicitly and retain the underlying failure.

`business_behavior_verified` remains false to avoid claiming broad business or
persistence correctness. `approved_http_expectations_checked` marks completed HTTP
comparison only. Finite tested conditions do not establish universal correctness.
No Meta request or repair is introduced by this increment.

## Validation and next work

Unit checks cover schema delivery, strict admission, source/policy drift, unsafe
routes/extra fields, body bounds, missing contracts, strict equality and distinction
between failed expectations and transport errors. Live authored Java/Python controls
use the same schema/checker: preserving and violating services both return health
200 and API 200, while only the response value distinguishes them. Both variants
are tested twice against fresh baselines. A wrong baseline control must stop before
candidate execution. These are executor controls, not an independent benchmark or
evidence of AI contribution; the proposed experiment is deliberately supplied.

The next task is source-aware investigation using this complete interface and
approved expectations, with finite paid selection and evidence-referenced diagnosis.
Keep source/expectation review explicit; do not embed a known bug, desired finding,
experiment answer or healthy repair in project adapters. New evaluation must be
registered separately, with healthy controls established before use and every
rejection/abstention preserved. Do not rerun v2 as fresh discovery or tune until a
favorable outcome appears.
