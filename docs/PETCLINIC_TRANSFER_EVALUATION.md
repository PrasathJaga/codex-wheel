# Prospective PetClinic transfer evaluation

Status: protocol, registration and packaging implementation. No real case has
been prepared/registered and no paid investigation, comparison or repair has run.
Method execution is disabled in this protocol revision. Before preparing fresh
cases, bind and verify the method runner and response/citation validation in the
final execution freeze. This package alone is not a completed evaluation system.

## Fixed foundation and pilot rules

The foundation is merged PR #41 at
`1a82fdb6cdcfdbe545bf3711c084a5242edc49ba`. Existing adapter, source intake, SQL
oracle, tests, control plans and workflow are verified against their actual hashes.
No previously verified component is edited by this package. The new protocol also
binds registration code, prompts, tests and the new registration-only CI workflow.
Protocol digests are anchored by the reviewed Git revision; replacing both a JSON
file and its neighboring digest is not cryptographic authentication.

The planned pilot has two neutral case IDs: one contract-breaking and one
contract-preserving change, selected before outcomes. Full outcomes and expected
labels require independent adjudication; registration of a commitment does not
establish ground truth. Existing upstream tests stay unchanged. A defect caught
by JUnit remains in the results; do not remove tests or discard that case.

| Method | Planned calls per case | Completion ceiling | World ceiling |
| --- | --- | --- | --- |
| Source-aware conventional | 0 | Not applicable | 24 |
| Simple Meta | 1 selection | 20,000 | 24 |
| Wheel Meta | 1 selection + 1 diagnosis | 12,000 + 8,000 | 24 |

At most six investigation/diagnosis requests for the pilot. Up to two separately
eligible one-request repairs would make the overall ceiling eight. Repair is not
enabled or automatically run here. Completion limits are ceilings, not targets;
prompt-token totals and actual spend differ. Record exact request parameters,
usage, latency and unknown costs. Availability/accounting must be checked before
paid execution using the owner's existing authorization.

One world is one fresh service/database execution. Healthy controls and repeated
base/candidate executions count against the ceiling; builds/setup are separate.
The conventional method may select at most eight source-aware plans before
execution. Search stops at its first independently verified violation, followed by
three fresh baseline/candidate pairs. Meta selects one plan and cannot replan from
feedback in this version. With two healthy control worlds, eight exploration pairs
and three fresh repeat pairs exactly exhaust 24 worlds. Methods may use fewer.

This compares whole workflows, not equal actual cost or a clean causal ablation
of orchestration. Shared relevant source context is fixed; conventional build/test
execution has full repository access. Report access and preparation differences.
Record whether the conventional method was independently developer-prepared or
AI-assisted; an assistant-written generator is not an independent human baseline.

## Case provenance and controlled intake

Cases use only existing allowed Java paths. Each replacement contains exact prior
content SHA-256 and replacement UTF-8 source; no arbitrary patch program, shell,
URL, new path or build/test edit is accepted. Full pinned baseline bytes are read
from a hash-verified archive. Candidate source is constructed as data, repackaged,
and passed through the unchanged complete-archive admission implementation.

Case preparation metadata is a declaration. `independent_developer` initially
produces `declared_unverified`; a separate reviewer must establish the actual
author/process. If we author cases ourselves, report internal transfer, not blind
independent evaluation. No external person is contacted automatically.

Commit before inference to separately retained expected labels, withheld checks
and reference repair metadata. Put their canonical hash in
`expectation_commitment_sha256`, not their contents in the case envelope. The
model payload is built from an explicit allowlist: public contract, action
interface, four baseline/candidate Java sources and diff. Labels, provenance,
commitments and reference checks are excluded. A large payload is rejected rather
than silently truncated. Public code may have appeared in model training.

The registry rejects duplicate identities, replacement registrations and exhausted
case budgets. The attempt helper rejects unregistered methods/cases and resampling.
On-disk registration uses an exclusive lock and atomic registry replacement;
existing evidence directories are never overwritten. Crashed locks/pending writes
require inspection, not automatic deletion/retry. These controls preserve local
history; a person who rewrites all reviewed files is outside this trust boundary.

## Commands

Verify protocol and all pinned components without inference or external execution:

```bash
python -m preflight.petclinic_evaluation
```

After the final execution freeze and case preparation, register a case:

```bash
python -m preflight.petclinic_evaluation --case case.json \
  --baseline-archive upstream.tar.gz --output case-bundle
```

The default registry is `evaluation/petclinic_transfer_registry_v1.json`; a separate
registry can be supplied with `--registry`. Outputs contain registration metadata,
the filtered model input, normalized baseline/candidate archives and the original
constructed candidate archive. Only admitted public/candidate source belongs in
external build inputs. Never mount this package, Wheel checkout or credentials
inside the service container. This CLI makes no API call or service execution.

Required case shape (schematic; placeholders are not accepted commitments):

```json
{
  "id": "pc-001",
  "infrastructure_revision": "1a82fdb6cdcfdbe545bf3711c084a5242edc49ba",
  "preparation": {
    "kind": "internal_transfer",
    "author": "actual preparer",
    "provenance_sha256": "64 lowercase hexadecimal characters"
  },
  "expectation_commitment_sha256": "64 lowercase hexadecimal characters",
  "replacements": [{
    "path": "one approved existing Java path",
    "before_sha256": "exact original content SHA-256",
    "content": "complete replacement Java source"
  }]
}
```

## Outcomes and repair boundary

Keep unsupported change, inconclusive investigation, execution error, invalid
baseline, confirmed violation and no violation observed distinct. Provider errors,
invalid output and abstentions remain in the denominator. Do not count diagnosis
prose as discovery, or repeated execution as independent investigator trials.
Infrastructure recovery must be separately registered; no retry to a good result.

Repair requests will start a fresh conversation with candidate source, public
intended behavior/tests and authenticated execution effects. Exclude baseline
source, unified diff, prior investigator conversation, reference repair and withheld
checks from that request. Baseline execution outcomes are allowed. This withholds
the supplied healthy implementation while preserving causal outcome evidence;
it cannot establish that public source was unseen during training. Acceptance
must preserve intended new behavior, unchanged tests, original reproducer,
healthy controls and independently prepared checks. Restoring only old behavior
must fail if it removes an intended new capability.

Report counts with denominators, false alarms on preserving cases, failures,
abstentions, execution/usage cost, setup and review effort. Two cases provide an
early bounded evaluation, not a population success rate or proof of superiority.
