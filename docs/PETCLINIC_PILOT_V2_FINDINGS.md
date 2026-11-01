# PetClinic v2 pilot: preserved negative evaluation, 1 November 2026

The run completed successfully as infrastructure. It did **not** establish a
successful Meta investigator, a valid benign-control comparison, superiority over
conventional testing, or a verified repair. These distinctions apply even though
the GitHub workflow is green.

## Evidence identity and reproduction

- Registered cases/launcher commit: `f6025cfbd9315ceb89a34182db4614a5406b8c5f`.
- PR44 merge: `33f213b1125f4782100043702c07c358a775a4fb` (same source tree).
- Run: https://github.com/PrasathJaga/codex-wheel/actions/runs/41235156422
- Artifact: https://github.com/PrasathJaga/codex-wheel/actions/runs/41235156422/artifacts/13056026837
- ZIP SHA256: `87e8be18858501b5f11c8dd498400b8b2b384304248666dd7b3da9ee6b35d946`.
- Protocol SHA256: `15a493eceaa73c71c89a64b9e1ed15fc0e0d60f597646388f32c1838f63a282e`.

Download the artifact ZIP without unpacking or executing it, then run:

```bash
python -m preflight.petclinic_pilot_audit --archive /path/to/artifact.zip --output /tmp/pilot-review.json
WHEEL_PILOT_RESULT_ARCHIVE=/path/to/artifact.zip python -m unittest discover -s preflight_tests -v
```

The auditor checks the pinned ZIP digest, exact registered cases/expectations,
method order, attempted-method registry, world identities and hashes, raw selection
admission, and usage accounting. It never executes public source or requests a
model. Its successful exit indicates a completed integrity audit; the explicit
`evaluation_ready_for_repair_or_superiority_claim` field remains **false**. Hash
agreement does not independently prove that the oracle or business contract is
correct. The full reproducible machine report is
`evaluation/petclinic_pilot_v2_results.json`.

## Every result

| Case | Prospective prediction | Conventional | Simple Meta | Wheel Meta |
| --- | --- | --- | --- | --- |
| pc-001 | preserving | confirmed violation, four paired trials | inconclusive: rejected proposal | inconclusive: abstained |
| pc-002 | violating | confirmed violation, four paired trials | inconclusive: rejected proposal | inconclusive: rejected proposal |

Both baseline and candidate `mvn verify` runs returned 0 for all six methods, with
upstream tests unchanged and no skipped-test packaging fallback. The conventional
method selected its first predeclared experiment in each case. Baseline trials
returned HTTP 204 for the valid update; candidate trials returned HTTP 500 in all
four paired repetitions. This is a concrete gap in those existing tests under
these conditions, **not** evidence of Meta adding discovery value: the conventional
plans found both failures, and Meta ran no admitted proposed experiment.

There were 28 attempted worlds: ten per conventional method and two baseline
control worlds for each of four Meta methods. Repetitions are confirmations, not
additional independent discoveries.

## Unexpected failure and incorrect prospective control

Evidence: `pc-001/source_aware_conventional/runtime/world-4/service.log`, and the
corresponding pc-002 log, record:

```text
NullPointerException: Cannot invoke "java.util.Collection.size()" because "c" is null
at java.util.HashSet.<init>(HashSet.java:120)
at org.springframework.samples.petclinic.model.Pet.setVisits(Pet.java:92)
at org.springframework.samples.petclinic.mapper.PetMapperImpl.toPet(PetMapperImpl.java:86)
at org.springframework.samples.petclinic.rest.controller.v1.PetRestControllerV1.updatePet(PetRestControllerV1.java:80)
```

Both changes call `PetMapper.toPet(PetDto)`. The observed stack shows failure
while mapping null visits, before the controller copies fields or saves. The
request omits visits. This is not the originally predicted ownership persistence
failure. It supplies no evidence of reassigned ownership, deleted visits, or
production data loss. The recorded post-action database snapshot agrees with the
initial state; the failed-world path does not record an after-stop final snapshot.

The internally authored preserving prediction was wrong. Preserve that prediction
and mismatch; do not relabel pc-001 as an initially known violating case or score
this as a false positive against valid independent ground truth. There is no
validated preserving control in this pilot. The withheld pc-002 reference repair
uses pc-001 content, so it is also unsuitable as a verified healthy repair.
No repair phase should proceed using it.

## Paid Meta results and integration defect

Four real `muse-spark-1.3` Standard responses were received: one per Meta
case/method. No diagnosis request followed because no proposal was admitted.

- Both Simple Meta proposals used `operation`/`reference` action fields instead
  of the validator's `op`/`pet` fields.
- Wheel pc-002 returned a plan array with `ref` fields instead of the required
  `{protocol, actions}` object and `pet` fields.
- Wheel pc-001 abstained, reasoning that the refactor preserved editable fields;
  this missed the runtime mapper failure.

The original model interface enumerates operation names and input bounds but
omits the exact per-action JSON field schema and a complete plan example. That
is an integration deficiency in our input contract. The strict validator rightly
rejected unsupported shapes; do not normalize these responses afterward and
count them as successful v2 experiments. The auditor replays the recorded
responses against their original payload and separately checks plan admission.

Reported totals: **45,438 prompt tokens; 10,006 completion tokens; 55,444 total**.
Usage-based Standard token estimate in the receipts: **US$0.099323**, with no
reported cached input. This is an estimate using the pricing basis preserved by
the pilot, not a verified invoice or remaining account balance. No additional
paid requests or retries were made during this audit.

## Next protocol, before any fresh paid evaluation

1. Keep v2 cases, predictions, raw receipts, prompts, verdicts and reference
   commitments unchanged. Treat this pilot as counterevidence, not a success
   story or independently blinded benchmark.
2. Prepare a separately versioned input interface with explicit closed JSON
   schemas for the plan and both action types: `op`, `pet`, and the update's
   `name`, `birth_date`, `type`. Include one neutral valid example; validate it
   against the same strict adapter before freezing the new protocol.
3. Add a local readiness check that distinguishes valid schema/payload delivery
   from a model's actual ability to investigate. Keep rejected proposals and
   abstention first-class results; do not add permissive aliases or hidden retry.
4. Establish a genuinely preserving control and a healthy repair target by live
   baseline/candidate verification before declaring new evaluation predictions.
   Any reused v2 case is now known and belongs to development/regression work,
   not fresh discovery. A fresh evaluation needs new precommitted cases and
   unchanged conventional tests; independent preparation is still outstanding.
5. Declare new budgets and source visibility before a new run. A repair phase
   must use a valid target, bounded edit checks, unchanged failing conditions and
   independent persistence verification. Do not claim a supplied-answer restore
   demonstrates general repair.

This PR adds the offline review and records the blockers. It does not modify the
frozen v2 investigator, validator, source fixtures, workflows or paid-call guards.
External code continues receiving neither Wheel source nor project credentials.
