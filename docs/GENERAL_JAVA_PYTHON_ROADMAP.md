# Reusable Java/Python investigation roadmap

Revised 1 November 2026 after the paid PetClinic v2 pilot. This is the active
engineering roadmap for broader project support. It supersedes the *future-work*
sequence in `PETCLINIC_PILOT_V2_FINDINGS.md`; it does not replace or revise any
historical protocol, case, prediction, receipt, result or audit.

## Objective and current limit

A developer supplies a Java/Python baseline, proposed change, project environment
and intended business expectations. Wheel investigates a plausible interaction,
freezes an experiment, executes both revisions, verifies the observed behavior,
and proposes a bounded repair when justified. GitHub presents evidence and clear
unsupported/inconclusive/error outcomes. Existing tests remain part of the process.

Broad Java/Python applicability is the product direction, not a current claim
that every project works. Language recognition does not establish build support,
runtime availability, behavioral correctness or safe execution. Proprietary
services, native dependencies, credentials and missing business expectations may
require configuration or make a project unsupported. Never hide these boundaries.

The current public-project pilot established execution and conventional detection
under bounded PetClinic conditions. It did not establish Meta discovery,
superiority, a healthy preserving control or a working repair. Both failing
candidates passed unchanged Maven verification. Retain all of that counterevidence.

## Rules that apply to every project

- One versioned investigator/validator/verifier process. Adapters describe how to
  build, start, address, observe and reset an application; they must not supply
  the defect, distinguishing sequence, desired verdict or repair answer.
- Hash complete source inventories, including test/build/config changes. Report
  those changes; do not silently discard them or assume all projects permit the
  same edit paths. A supported pair policy separately decides execution admission.
- Derive interfaces and dependencies from source and declarative configuration.
  Model suggestions remain hypotheses; execution and independent observations
  establish findings. Intended changes are judged against declared expectations,
  not against an assumption that every difference is a regression.
- Business expectations need an explicit, attributable source: developer-provided
  contracts, approved existing contracts or reviewable inferred candidates.
  Missing or ambiguous expectations require clarification/abstention. Do not
  invent refund, ownership, financial or temporal rules for unfamiliar projects.
- Give Meta complete closed JSON tool schemas and neutral examples validated by
  the same strict admission code. Never accept aliases after seeing a response
  or feed conventional answers, expected labels or reference repairs into inference.
- Preserve every attempted request, malformed proposal, abstention, build failure,
  execution error and mixed trial. Distinguish application failures under a valid
  experiment from infrastructure failures. No retry until a desired result appears.
- External code runs only within reviewed isolation, without Wheel source,
  project credentials, host mounts/home or Docker socket. Static discovery does
  not execute/import project modules, wrappers, plugins or install hooks. Source
  is never automatically uploaded to a model merely because it was discovered.
- Ordinary PR checks are unpaid. Paid work requires a declared finite experiment
  and accounting; existing authorization does not remove those bounds. Report
  invoice-unknown costs honestly. Keep automatic generic paid operation disabled.

## Delivery stages and gates

| Stage | Deliverable | Evidence required to advance |
| --- | --- | --- |
| 1. Project discovery | Authenticated archive pair, complete source identities/change inventory, build-layout recognition and explicit configuration gaps | Deterministic results on unrelated layouts; malformed archives/metadata fail safely; zero project execution/model calls |
| 2. Execution manifest | Versioned configuration for project roots, reviewed build/test/start commands, runtimes, dependencies, health/reset, resource/network limits and secret-free observers | Same schema across Java/Python; unknown commands/services are not executed; configuration cannot encode a defect/answer; protected source and credentials remain excluded |
| 3. Generic isolated execution | Build both immutable revisions; retain existing test results; run/reset selected services under a shared executor | Live healthy Java and Python applications, negative environment controls, repeated clean state; real CI evidence beyond mocked tests |
| 4. Source-aware investigation | Source/interface/dependency extraction and complete bounded HTTP/operation tools; one model-selected experiment | Exact schema delivery; valid proposed and abstained/rejected outcomes preserved; no domain-specific experiment hints; only declared endpoints/actions/resources |
| 5. Independent behavioral verification | Compare baseline and candidate using approved expectations, response evidence and separately read persisted effects | Baseline valid, intended changes accounted for, repeated paired trials, causal evidence; model prose never determines verdict |
| 6. Generic bounded repair | Candidate-source edit proposal without healthy source supplied; source policy, unchanged tests, failing experiment and relevant controls | Repair passes under original conditions; no weakening tests/oracle; failed repairs retained; finite limits and explicit tested coverage |
| 7. Frozen transfer evaluation | Unfamiliar independently prepared changes, healthy controls and source-aware conventional comparison | Same process and comparable access/budgets; all outcomes/costs/times retained; no tuning after exposure; development cases excluded from fresh discovery claims |
| 8. Workflow and usability | General admission/results in GitHub, evidence report, actionable setup instructions | Real supported PR, explicit unsupported/error paths, permissions/stale-result checks and an external developer onboarding attempt |

Work one stage at a time. A stage's implementation is not its validation. Missing
access, invalid baseline, integrity failure or exhausted budget stops the dependent
stage. Scope expansion needs an explicit plan revision, not an ad hoc bypass.

## Stage 1 implementation in this PR

`preflight.project_discovery` takes two authenticated tar.gz source archives,
their expected SHA256 values, and explicit archive roots. It reuses the existing
bounded regular-file archive validator without changing frozen PetClinic code.
The reused collector is structurally generic: it has no project-specific path
allowlist or execution behavior. This avoids introducing a second archive parser.

It recognizes literal Maven POM and Python pyproject metadata; enumerates Gradle,
setup.py/setup.cfg and requirements.txt as configuration signals without evaluating
them; identifies multiple roots; counts Java/Python files; hashes the complete
source inventory; and includes changes to tests/manifests as well as source.
Common generated/environment directories are excluded only from *discovery*,
never from source identity or the change inventory. No framework, route, dependency
or runtime readiness is inferred from language/file names alone.

All recognized projects remain `ready_for_execution=false`. Malformed metadata
is explicit. No profile inherits the PetClinic action interface, database schema,
path-edit policy, expected verdict or known repair. This module is not wired into
paid workflows and cannot execute arbitrary project commands.

```bash
python -m preflight.project_discovery \
  --baseline-archive /path/to/base.tar.gz --baseline-sha256 BASE_SHA256 --baseline-root base-root \
  --candidate-archive /path/to/head.tar.gz --candidate-sha256 HEAD_SHA256 --candidate-root head-root \
  --output /tmp/project-discovery.json
```

An unchanged pair is permitted for onboarding and explicitly has no changed paths.
A recognized project still needs the Stage 2 manifest and Stage 3 live executor.
Current recognition covers source-bearing Maven, pyproject, Gradle and setup
layouts, not every build dialect or monorepo structure. Archives retain the
existing bounded size/count restrictions and reject links/special files.

Tests include mixed Maven/Python roots, declarative metadata, Gradle/setup content
that must never execute, XML declarations, malformed TOML/XML, archive tampering,
symlinks/traversal, generated directories, deterministic identities and all change
kinds. The actual pinned public PetClinic source is an optional local replay;
synthetic layouts establish parser behavior only, not real project transfer.

## Next concrete work

The shared manifest shape/reference validator is now implemented in
`preflight.execution_manifest` (see `EXECUTION_MANIFEST_V1.md`). It performs no
execution and deliberately returns configuration-valid-but-unready. Next review
the trusted image/command/network admission policy and implement the generic
isolated executor, then validate healthy execution for both languages. Only afterward version the complete investigator interface and
register a new investigation. Known PetClinic failures remain useful regression
inputs, but repeating them cannot establish unfamiliar discovery or independent
repair ability. A healthy control must be validated before it is used as a control;
it cannot be declared healthy based on source intuition again.

Measure setup edits/time, build and execution success, proposal admission,
confirmed findings, abstentions/errors, conventional comparison, repair outcomes,
turnaround and token cost. Publish denominators and unsupported attempts. A tie
or a conventional win is valid evidence. No fixed judging score, production loss,
savings or universal correctness claim follows from these milestones.

## Stage 3 runtime increment

`preflight.isolated_executor` now implements the offline build/test-only subset;
see `ISOLATED_EXECUTOR_V1.md`. Service/dependency/observer execution and network
fetching are rejected. Dedicated live Java/Python controls are required before
calling this subset runtime-verified; this does not complete the full Stage 3 gate.
