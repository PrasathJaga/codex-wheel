# Bounded PetClinic profile adapter v1

This interface is limited to the pinned PetClinic profile-update contract. It is
not a general HTTP agent, arbitrary Java repository intake or a completed fresh
investigation. No candidate mutation or paid inference is introduced here.

## Frozen experiment interface

A plan has only `protocol` and `actions`. There are at most eight actions:

| Action | Permitted inputs |
| --- | --- |
| READ_PET | visited_pet, unrelated_pet or missing_pet |
| UPDATE_PET_PROFILE | visited_pet or missing_pet; bounded name; ISO birth date from 2000–2025; original_type or alternate_type |

The host resolves typed references from the seed, generates exact API paths and
request bodies, and independently derives expected effects. Empty names select
the existing invalid-input control. The missing reference uses a checked absent
sentinel. The original type always means the initial seed's type, not the most
recent type. Arbitrary URLs, methods, SQL, shell commands, unexpected keys,
unbounded payloads, and non-profile operations are rejected before execution.

At least one valid target update is required; runtime rejects vacuous experiments.
Repeated identical valid updates are supported and must preserve state. Every
action is followed by an independent committed-state SQL snapshot. HTTP success
without the expected effects, unrelated writes, changed owners, or lost visits
produce a violation. Rejected input and reads must leave state unchanged. Response
text and actual state remain in the action event even when verification fails.
GET response-body semantic equivalence is not yet an assertion: the contract in
this version checks HTTP status and committed state.

Plans are validated, copied and hashed before execution. Replay checks both the
plan's self-consistency and a separately trusted expected digest. The freeze lock
binds component files and public control-plan digests. This is a revision-bound
integrity contract, not a digital signature or authentication of an untrusted
replacement lock. Evaluation runs must pin the reviewed lock/repository revision.

Two different public healthy plans are supplied to exercise rejected input,
missing target, reads, type changes and repeated updates without driver edits.
These plans are setup controls, not held-out discoveries or a conventional
comparison. They run against the same healthy upstream revision and fresh seeds.

## Candidate boundary

The admission helper compares complete trusted path/SHA-256 maps, allowing edits
only in PetRestControllerV1.java, PetMapper.java, Pet.java and ClinicServiceImpl.java.
Additions, deletions and changes to tests, build configuration or other files are
unsupported. An unchanged pair is admitted as a control. The caller must build
the COMPLETE maps from verified source bytes; model-supplied/subset maps are not
trusted. Symlink/file-type handling belongs to that source collector.

Complete source collection, normalization and separate candidate builds are added
by the source-intake work package; see PETCLINIC_SOURCE_INTAKE.md. Its live case is
an unchanged-source control. External fork acquisition and arbitrary PR intake
remain disabled. A passing control does not establish changed-pair investigation.

## Execution and non-exposure

Adapter and verifier execute on the trusted host, embedded byte-for-byte in the
workflow and checked against the reviewed modules. Neither is mounted in the
external service. Its read-only work volume contains upstream build output only;
it receives temporary application database credentials and no Wheel/GitHub/Meta
credentials. The separate SQL role and private internal network remain unchanged.

The existing refund/inventory protocol files and historical evidence are unchanged.
The prior PostgreSQL readiness failure remains documented. This PR adds a freeze
candidate: after live tests pass and merge, pin that revision before fresh cases.
Changes to the interface or verifier during evaluation require a new version and
separate reporting; never silently tune the frozen interface to a case.
