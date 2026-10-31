# PetClinic transfer runner v2

This adds the actual bounded selection/diagnosis gateway, paired adjudication,
source-aware conventional plan executor and an isolated Docker world implementation.
There are still no real registered cases and no fresh paid investigations. V1 is
preserved as historical registration; v2 binds the runner before fresh cases.

## What is checked

The gateway uses the existing admitted Meta endpoint/model/client request pattern:
Muse Spark 1.3, zero SDK retries, low reasoning effort and the registered completion
limits. Each phase writes an exclusive receipt BEFORE requesting. An existing
receipt or claimed case/method prevents resampling, including after uncertain
process termination. Provider exception bodies/headers are not persisted; raw
model responses, usage, finish reasons and safe failure types are retained.
Unknown dollar cost remains null. A failed request is an attempted request, not
proof that the provider charged for it.

Proposal validation checks exact fields, permitted plan inputs and 2–6 exact
source ranges covering baseline/candidate. The host resolves recorded source
lines; a valid citation is not proof that the hypothesis is semantically correct.
Abstention, malformed JSON, duplicate keys, truncation, unsupported tools and
invalid references are preserved without retry. Diagnosis references must resolve
to actual world/action event IDs. Diagnosis can neither upgrade a healthy result
nor erase an independently confirmed failure. Its semantic review remains human.

Two baseline control worlds precede inference. A Meta-selected plan then runs one
initial pair plus three fresh pairs. A violation needs healthy baselines, identical
initial seeds and a candidate violation in every pair. Mixed outcomes are
inconclusive, not another reason to resample. Baseline failure stops before further
paid work. Execution errors remain errors. All worlds, including controls and
unsuccessful attempts, count before execution against the 24-world ceiling.

The conventional runner accepts up to eight distinct source-aware proposals fixed
before outcomes. It records preparation provenance, then searches in declared
order and repeats the first finding in three fresh pairs. Its worst-case eighth
discovery consumes exactly 24 worlds. AI-assisted plans must be described as such;
declaring an independent author is not independent validation.

## Source and execution isolation

Each source side is built in a separate disposable volume from hash-verified
admitted archives. Baseline Maven verify must pass. A failed candidate verify is
retained; packaging with skipTests may permit observation, but never changes that
test outcome to passing. Packaging/compile failures stop observation as execution
errors. This policy matches the need to retain cases already caught by tests.

The subprocess environment forwards only PATH/LANG and specifically allowed
disposable database passwords. The Meta key is removed from the parent environment
into the trusted client before any build. Service containers receive only their
upstream build volume, temporary app/database access, limits and an internal
network. No Wheel checkout, verifier module, host home or Docker socket is mounted.
The SQL role and verifier stay outside the service; read-only access is checked.
Build networking downloads public dependencies and is not an egress allowlist.
Host/kernel and reviewed runtime images remain trusted; this is not arbitrary
hostile-code or multi-tenant admission.

The GitHub smoke job itself never checks out Wheel. Reviewed executor code runs on
the trusted host through the workflow, never inside the service. It builds and
executes the two public healthy plans on both unchanged source sides: four live
database worlds with zero provider requests. Model gateway tests use explicit test
doubles; their simulated findings are not scientific evaluation results.

## Commands and preparation order

Install the existing admitted SDK range only in the trusted environment when paid
execution is actually needed (`openai>=2,<3`). No SDK or model key is needed for the
unit tests, protocol self-check or healthy Docker smoke.

Verify v2 without inference:

```bash
python -m preflight.petclinic_meta_runner
```

After the merged runner and live checks pass, pin that reviewed revision, prepare
the two fresh cases, and commit their expected-label/check/provenance commitments.
Use the v2 infrastructure revision from its protocol, not the old v1 case example.

Register a case without calling Meta:

```bash
python -m preflight.petclinic_meta_runner --register-only \
  --case case.json --baseline-archive upstream.tar.gz --output registered-case
```

Run one registered method in a trusted environment with Docker. Meta methods use
the already-authorized MODEL_API_KEY environment input. Check current access and
accounting before execution; do not infer available credit from old records.

```bash
python -m preflight.petclinic_meta_runner --case case.json \
  --baseline-archive upstream.tar.gz \
  --registry evaluation/petclinic_transfer_registry_v2.json \
  --method wheel_meta --output wheel-result
```

`simple_meta` selects the one-call comparison. `source_aware_conventional` makes no
model request and additionally requires `--conventional-plans plans.json` containing
case_input_sha256, preparation (kind/author/provenance_sha256), and experiments.
Each experiment has the same propose/hypothesis/source_refs/plan shape as a valid
Meta proposal. Preserve the preparation effort and unequal access/usage honestly.

The persistent registry claims a method before execution; output directories and
receipts cannot be silently replaced. Crashed attempts remain claimed and require
separately registered recovery, not a second invocation. Result files include the
case/protocol binding and raw build outcomes. API failures never print credentials.

## Current boundaries

There is no automatic paid GitHub trigger in this PR. The verification workflow is
unpaid. A paid GitHub deployment must preserve the separate trusted/external worker
boundary; do not simply add secrets to the external smoke job. The local runner
requires an admitted registered case; the repository's v2 registry starts empty.

Fresh discovery, comparative advantage, external developer usefulness and repair
remain unmeasured. Repair is disabled in v2 and requires its separately declared
candidate-only input and verification phase. Do not call a test-double response a
paid Meta response or the four healthy worlds unfamiliar-case evaluation.
