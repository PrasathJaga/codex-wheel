# Generic isolated executor: first runtime capability

Stage 3 begins with **offline build/test projects**, using the shared manifest
from Stage 2. This is a reusable executor, not an investigator or general runtime
for all Java/Python applications. Services, databases, persistence observers,
network dependency fetching and repository executable wrappers are explicitly
unsupported in v1 and rejected before Docker runs. Existing domain executors and
historical paid evaluation remain unchanged.

## Inputs and trust boundary

`preflight.isolated_executor.run_pair` and its CLI take authenticated baseline and
candidate tar.gz archives, their hashes/root names, the shared execution manifest,
and a separately trusted local execution policy. It recomputes discovery directly
from the actual archives and validates the manifest against that report. The
policy binds the exact manifest hash and an image-digest allowlist, caps repetitions
at 1–3, and sets a total action budget of 10–1800 seconds. Example policy shape:

```json
{
  "schema": "wheel-local-execution-policy-v1",
  "manifest_sha256": "<canonical digest of reviewed manifest>",
  "allowed_images": ["<reviewed image name>@sha256:<64 hex digits>"],
  "max_repetitions": 2,
  "total_timeout_seconds": 600
}
```

Placeholders are not valid policy values. The policy must originate outside the
external source/model response. There is no cryptographic signature or interactive
approval service: the caller must enforce the trusted policy boundary. A project
must never be allowed to approve itself by submitting a matching policy. Image
presence/provenance and exact source/command/network review are prerequisites.
The executor does not pull images. A digest proves identity, not image safety.

The source descriptor has exactly `baseline_sha256`, `candidate_sha256`,
`baseline_root`, `candidate_root`. The discovery report used to prepare the manifest
must come from these same archives. Build/test commands remain opaque untrusted
code: they can execute arbitrary instructions **inside** their reviewed sandbox.

```bash
python -m preflight.isolated_executor \
  --baseline /path/base.tar.gz --candidate /path/head.tar.gz \
  --source /path/source.json --manifest /path/manifest.json \
  --policy /path/trusted-policy.json --output /tmp/new-execution-result \
  --repetitions 2
```

Output must be new. Admission errors stop before Docker/materialization. Runtime
errors and failed tests retain `result.json` and available logs. CLI exits nonzero
for candidate check failure, invalid baseline or execution error. The smoke harness
can separately assert expected negative controls without calling them successful
application runs.

## Execution and non-exposure

Each revision/project/repetition gets a new named volume. Only a reconstructed
regular-file archive from the admitted external source is materialized, in a
trusted temporary directory outside the checkout. The extraction container mounts
that single archive read-only and its disposable work volume. Application command
containers mount only the disposable volume. Wheel source, host home, credentials
and Docker socket are never mounted into external containers.

A trusted `chown` helper initializes an empty volume with only CHOWN capability;
it receives neither source archive nor project code. Extraction and project
commands run as UID/GID 1000 with all capabilities dropped, no-new-privileges,
read-only root filesystem, resource limits and `--network none`. Only the work
volume and bounded temporary filesystem are writable. Startup inspection checks
the actual user, network, root filesystem, capabilities and exact mount set before
project execution. Command exit status is checked from container state, independently
of Docker CLI success; OOM is an execution failure.

The host-side Docker subprocess receives a minimal environment and a fresh empty
Docker config directory, avoiding host API keys, Docker auth and proxy settings.
Only reviewed digest-pinned locally present images are used. Image built-in
configuration is still part of image review. No model calls occur.

Commands have individual timeouts; worlds and the complete run have deadlines.
Docker output is capped at 2 MiB per operation. Captured partial output is preserved
on timeout/overflow. Control-state queries and cleanup have separate bounded
operation timeouts; overall wall-clock duration may include cleanup after the
execution deadline. Every created container is removed and each disposable volume
is removed in `finally`; cleanup failure makes the run an execution error. This
is Docker isolation on a trusted runner, not protection against container/kernel
escape or an independent security certification.

## Outcomes and evidence

- `build_and_tests_passed`: configured checks passed on both revisions under these
  offline conditions. It is **not** a business-contract verdict.
- `baseline_invalid`: a baseline build/test failed; dependent candidate execution
  stops. No passing healthy baseline is manufactured.
- `candidate_checks_failed`: candidate build/tests failed; failure retained, no
  skipping tests, fallback packaging, patching or retry. Declared repetitions are
  recorded, including mixed outcomes; one failure prevents an all-pass result.
- `execution_error`: infrastructure, timeout, output limit, OOM, isolation mismatch
  or cleanup failure. Do not count it as reproduced application misbehavior.

Evidence includes original source identities, manifest/discovery/policy hashes,
per-world volume identity and side/trial/project, inspected mount/isolation
configuration, command phase/index, exit status and logs. `business_behavior_verified`
is always false. Arbitrary project log content is untrusted text, never instructions.

## Live controls and limits of the claim

`preflight.executor_smoke` is a trusted, internally authored CI harness. It exercises
healthy Python unittest and Java source-launcher checks twice on each revision,
checks for fresh state and absence of private mounts/keys, and retains failing
candidate controls for both languages plus an invalid Python baseline control.
These examples validate executor mechanics; they do not prove unfamiliar project
transfer, Maven/Gradle dependency resolution, Meta discovery or repair.

CI pulls public Python/Temurin control images on the trusted host, resolves their
immutable RepoDigests and records those digests in the generated manifest/policy
artifacts. The tags are acquisition inputs for controls, not pre-reviewed fixed
production image pins; subsequent pulls can resolve differently. External commands
never pull or use network. No API-key secrets are supplied to this workflow.

Local unit checks validate policy binding, admission boundaries, isolation flags,
actual inspection rejection and container-exit/CLI-exit distinction. The local
workspace lacks Docker, so real runtime evidence must come from the dedicated
GitHub workflow. A green unit check alone does not satisfy the live gate.

Next stage: verify these controls, then add reviewed dependency acquisition and
service/dependency lifecycle with fresh-state and independent observer checks.
Only after those capabilities work should generic source-aware investigation be
connected. The failed PetClinic pilot stays counterevidence; no case-specific
prompt, alias repair, healthy-answer shortcut or paid resampling is introduced.
