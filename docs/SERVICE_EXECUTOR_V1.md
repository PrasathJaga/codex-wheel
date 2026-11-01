# Generic stateless HTTP lifecycle executor v1

This increment extends the shared Java/Python execution manifest to one stateless
HTTP service per revision. It does not complete Stage 3: dependency acquisition,
database/service dependencies, independent persistence observers, arbitrary
framework onboarding and behavioral investigation are still pending. Configurations
requiring dependencies, observers or environment bindings are rejected before Docker.
No new domain action interface, business oracle or paid workflow is introduced.

## Operation

`preflight.service_executor` recomputes discovery from authenticated archives,
validates the same execution manifest and requires a separately trusted policy:

- `schema`: `wheel-service-execution-policy-v1`
- `manifest_sha256`: canonical digest of the complete reviewed manifest
- `allowed_images`: reviewed immutable image references, already present locally
- `max_repetitions`: integer 1–3
- `total_timeout_seconds`: integer 10–1800

The policy is supplied by the trusted operator, never accepted as self-approval
from external source or the model. Hash binding does not establish provenance.
Source descriptors and CLI options match the offline executor:

```bash
python -m preflight.service_executor \
  --baseline /path/base.tar.gz --candidate /path/head.tar.gz \
  --source /path/source.json --manifest /path/manifest.json \
  --policy /path/trusted-service-policy.json --output /tmp/new-service-result \
  --repetitions 2
```

One selected project must declare `service`. Build and mandatory test commands
run offline first. Each world uses a fresh work volume and fresh internal Docker
network. The service uses that internal network, non-root user, dropped
capabilities, resource bounds and read-only root **and source/work volume**;
transient application writes belong in its isolated `/tmp`. No host ports are
published. Stateful files in the source tree, external services and dependency
fetching require capabilities not implemented here.

The extraction and build/test containers retain the existing offline executor's
no-network controls. Shared container inspection now accepts an explicitly named
network and read-only work mount; its defaults remain unchanged for offline runs.
The offline controls run again in CI to catch regressions.

## Health checks and evidence

The trusted controller reads the service address from Docker, checks that it
belongs to the one expected **internal** network and its private subnet, and checks
that no host port is published. HTTP probes address that IP/port and the reviewed
health path. They do not use environment proxies, credentials, cookies or redirect
following. This is a health check, not an agent conversation or business experiment.
Responses are capped at 64 KiB with a 2 KiB preview and full-body digest; each
completed probe/error is retained. Oversized responses cause an execution error.
Readiness polling stops at the configured deadline. Each probe runs in a trusted,
separately spawned HTTP worker with a hard parent deadline; a stalled worker is
terminated and joined, with kill fallback. This bounds slow-drip headers/bodies as
well as ordinary socket waits. Worker deadline/transport failures are recorded as
readiness attempts. These are health retries, not investigator resampling or paid
calls. Worker code belongs to the trusted controller; no external project code
executes on the host. Worker teardown and Docker control/cleanup operations can
add bounded overhead beyond the readiness deadline.

A service exiting during startup is distinguished from a health endpoint not
becoming ready. OOM and Docker/control failures are infrastructure errors. The
service is stopped before cleanup, its stopped state is checked, and logs are
retained. All containers, volume and network are removed in `finally`. Cleanup
failure becomes an execution error. The trusted host's API keys/Docker auth are
not passed to containers; only external source is mounted, never Wheel source,
host home, project credentials or Docker socket.

Statuses:

| Status | Meaning |
| --- | --- |
| `service_lifecycle_passed` | Both revisions passed configured checks and reached expected health in all declared worlds |
| `candidate_lifecycle_failed` | Candidate checks/startup/readiness failed; preserved without a passing substitute |
| `baseline_invalid` | Baseline failed its checks/startup/readiness; candidate execution stops |
| `execution_error` | Infrastructure, budget, isolation, output, transport or cleanup failure |

Per-world status distinguishes `build_failed`, `test_failed`, `service_start_failed`,
`health_not_ready` and `service_ready`. Original source, manifest, discovery and
policy hashes are recorded, alongside isolation settings, network/volume identity,
command exit statuses, readiness attempts, shutdown confirmation and logs.
`business_behavior_verified` remains false for every outcome. A healthy endpoint
does not establish correct persisted effects or any intended business expectation.

## Validation

Unit tests cover policy/source binding, unsupported dependencies, named-network
and read-only mount flags, private subnet/network membership, forbidden published
ports, redirect non-following and response size limits. The dedicated live CI
harness starts Python HTTPServer and Java HttpServer applications twice on each
revision, retains intentional candidate startup failures in both languages, and
checks invalid-baseline stopping. It checks missing private mounts/keys, fresh
per-world state, internal networking, confirmed shutdown and cleanup. These are
authored executor controls, not unfamiliar-project evaluation or Meta evidence.

Control image tags resolve to recorded digests on the trusted CI host as in the
offline controls. No project command downloads an image or dependency. Live Docker
validation cannot run in the local workspace; use the workflow artifacts to verify
the claimed milestone. Do not infer runtime success from unit-test success.

Next: complete bounded dependency acquisition and disposable database lifecycle,
verify actual observer permissions/fresh persistent state, then connect generic
source-aware investigation with a complete tool contract. Historical failed
PetClinic predictions and paid results remain unchanged.
