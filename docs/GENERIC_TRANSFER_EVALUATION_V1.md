# Generic transfer evaluation v1 — prospective comparison

Prepared 2 November 2026 after PR55's real Meta integration. That integration
produced three admitted experiments and one preserved abstention on known authored
controls. It does not establish unfamiliar transfer, independent preparation or
superiority over conventional methods. The failed PetClinic pilot remains intact.

This PR implements registration/admission and a comparison runner. **No new case
is registered, no unfamiliar evaluation has run and no new paid call is made.**
The empty registry is intentional: internal examples must not be relabeled as
external independent evidence to fill it.

## Freeze before selecting cases

`evaluation/generic_transfer_v1/protocol.json` and `protocol.sha256` bind the
unchanged 23 preflight modules from master
`848d02d807eea22f6b72a5ea257160b371284fe4`, and the new comparison-runner bytes.
No investigator prompt, strict tool schema, source admission, lifecycle executor,
HTTP checker or repair logic is changed. The comparison code lives outside the
preflight implementation so historical integration commitments remain unchanged.

Two fresh nonidentical source pairs may be registered: one Java and one Python.
This first comparison uses the existing **stateless HTTP** path. Postgres snapshots,
persistence predicates, dependency acquisition, unsupported build systems and
arbitrary projects are not silently admitted through this wrapper. Cases must
fit existing runtime/interface/expectation capabilities; do not add a capability
or hint after seeing a case outcome and call it the same evaluation.

Freeze the protocol commit before case preparation. The preparer supplies a
`prepared_after_protocol` commitment and provenance evidence; the reviewer must
check actual chronology. A hash/string alone does not prove when work occurred.
Known integration fixtures and unchanged baseline/candidate controls are not fresh
changes. A preserving **changed** case can qualify, subject to provenance review;
its intended status is an authored prediction until verified.

## Same execution opportunity, disclosed preparation

| Input/budget | Source-aware conventional | Wheel Meta |
| --- | --- | --- |
| Numbered source, diff and changed-path scope | Exact prepared packet | Same packet |
| Approved HTTP interface/expectations/tool schema | Same | Same |
| Selected experiments | One predeclared valid proposal | One model proposal or abstention |
| Actions per experiment | 1–8 | 1–8 |
| Lifecycle prerequisite worlds | Two | Two |
| Comparison | Two fresh paired trials, four worlds | Same |
| Maximum execution worlds per case | Six | Six |
| Provider requests | Zero | At most one selection + one diagnosis |
| Preparation effort | Record measured seconds or unknown | Execution/model time recorded; setup effort remains separate |

The conventional baseline is a source-aware **supplied plan**, not a weak random
search or empty test suite. Its preparation must be disclosed as human,
AI-assisted or deterministic source-aware. Citations, complete schema admission
and non-vacuous operation limits apply to its proposal too. Do not label an
AI-assisted packet an independent human baseline. Equal execution budgets do not
mean equal human effort or identical cost. Missing timing stays unknown; no
productivity claim may be derived from it.

Both methods run the same source/configuration, lifecycle controls, experiment
execution and independent checker. No conventional verdict or expected case label
is sent to Meta. The conventional plan's context hash must equal the exact Meta
context hash. The case label commitment and preparer metadata are outside that
context. Business expectations themselves must be explicitly approved and visible
to both; a difference alone is not automatically a regression.

The total maximum paid budget is four requests / 40,000 completion tokens for the
two Meta attempts. Existing SDK retry and context/time bounds remain unchanged.
No live CLI, SDK client or paid GitHub workflow is added by this PR. A separately
reviewed launch must enforce global attempt storage/history and report usage/cost;
a local registry is not a provider billing ledger.

## Case packet and independent review

`validate_case` requires exactly:

- `id`;
- `inputs`: authenticated baseline/candidate archive base64, source descriptor,
  execution manifest, lifecycle policy, interface, contract and investigation
  policy; the Meta attempt id is `<id>_wheel_meta`;
- `conventional`: `context_sha256`, strict proposed experiment with source refs,
  `preparation_kind`, `effort_seconds` (measured nonnegative integer or null);
- `provenance`: `kind`, `preparer`, `prepared_after_protocol`, `source_reference`,
  `effort_seconds`;
- `expectation_commitment_sha256`: canonical SHA256 of the separately retained
  intended-label/evidence record. Commit before execution; never feed it to Meta.

Origin kinds: `independent_authored`, `upstream_existing_change`, `internal_authored`.
Registration accepts internal packets for structural checks, but execution review
**rejects** them for this transfer evaluation. The committed registry remains
empty. Unit tests use declared synthetic trust witnesses; they are not external
cases or proof that a real independent review occurred.

A public historical change is independently authored source, but is not necessarily
unseen to a model or a blinded evaluation. Its adapter preparation and prior outcome
knowledge must be disclosed. Do not claim independent case preparation merely
because code came from another GitHub repository.

Register without execution:

```bash
python -m evaluation.generic_transfer_v1.runner \
  --case /path/to/reviewable-case.json \
  --registry evaluation/generic_transfer_v1/registry.json \
  --output /tmp/new-registry.json
```

Register both languages, review and commit the complete batch before any run.
Registration closes after an attempted method; full-batch execution admission
also prevents adding a second case after seeing the first result. Do not overwrite
an old registry or expectation record to repair unfavorable results.

A separate **trusted** review record binds `case_sha256`, `protocol_sha256`,
`provenance_verified=true`, a different `reviewer` and `evidence_reference`.
The runner validates shape, identities and eligibility; it cannot authenticate a
person, verify honesty, or replace review of the referenced external evidence.
The operator must control review/policy/claim storage, not the project or model.
These are not signatures or automatic proof of independence. Until evidence is
actually reviewed, case independence remains `unverified_requires_external_review`.

## Execution and retention

`run_method` invokes either the supplied conventional proposal or the unchanged
`run_investigation`. The caller supplies the separately trusted provider factory
for Meta; no client is silently constructed. Persistent exclusive claim files are
written before execution, including conventional attempts. Never delete claims
on failure. Registry changes must be persisted by the trusted orchestrator; the
claims prevent retry even if a registry save fails. A distributed orchestrator
must keep these stores durable and reconcile claims/results before further work.

Both languages must be registered before the first run. Each case/method may run
once. Unresolved claims/attempts, baseline/lifecycle/infrastructure failures or
provider diagnosis failure stop later comparison. An inconclusive proposal or
abstention stays an outcome and does not trigger a corrected proposal. Model
explanations do not overwrite verifier verdicts. Original raw responses, frozen
experiments, baseline/candidate observations, failures, cost receipts and source
identities remain in the reused investigator artifacts. Run-level reporting must
include every row and denominator, including setup failures and unsupported inputs.

The reported `execution_elapsed_seconds` includes build/lifecycle/execution (and
Meta time for that method). It does not measure a developer's entire investigation
or onboarding effort. A finite number of HTTP worlds cannot establish persistence
correctness, production incidence, financial savings or universal correctness.
No generic repair is introduced here.

## Non-exposure and remaining access gate

An external preparer only needs the public evaluation specification/tool interface
and their own repository inputs. Do not grant access to Wheel source, private repo
credentials or model keys. Do not push code, publish issues, run upstream CI or
send requests to people without separate authorization. External source continues
executing only in existing restricted containers without the Wheel checkout or
host credentials; this PR changes no mounts or runtime environment.

The remaining gate is **actual externally prepared/reviewed case evidence**. None
has been obtained in this task. We may prepare onboarding instructions, but may
not manufacture an independent participant or self-certify source familiarity.
After verified case intake, commit registrations and a concrete bounded launch
before spending. Retain a tie or conventional win. Do not promise a judging score.
