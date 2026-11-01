# Shared execution manifest v1

Stage 2 of `GENERAL_JAVA_PYTHON_ROADMAP.md`, implemented 1 November 2026.
This describes configuration validation only. No generic executor exists yet.
A successful validation is **not permission to run commands**, proof that images
are trusted, verification of dependencies, or evidence of correct behavior.

## Use

1. Generate the baseline/candidate discovery report from authenticated archives
   with `preflight.project_discovery`.
2. Configure both revisions using the same selected project roots and declared
   environment. Set `discovery_sha256` to the canonical JSON digest of that report
   (`preflight.petclinic_adapter.digest`). JSON whitespace does not affect it.
3. Run the validator, without installing or importing project code:

```bash
python -m preflight.execution_manifest \
  --manifest /path/to/execution.json \
  --discovery /path/to/project-discovery.json \
  --output /tmp/configuration-review.json
```

Result: `configuration_valid_requires_review`, bound manifest/discovery hashes,
validated configuration and explicit blockers. `ready_for_execution` is always
false. Missing/unknown fields, invalid references, duplicate JSON keys and inputs
larger than 1 MiB are rejected. Source discovery and manifest files must come from
the reviewed workflow: hashes bind contents but do not prove origin or approval.

## Closed configuration structure

All listed object fields are required. Additional fields are rejected. Identifiers
use `[a-z][a-z0-9_]{0,47}`. Paths are repository-relative and reject traversal;
project root `.` is allowed. Images use an immutable `name@sha256:<64 lowercase
hex digits>` reference. Image existence, provenance and allowlisting are future
executor admission checks, not properties established by this validator.

| Field | Shape and meaning |
| --- | --- |
| `schema` | Exactly `wheel-execution-manifest-v1` |
| `discovery_sha256` | Canonical digest of the complete discovery report |
| `projects` | 1–8 project objects, described below |
| `dependencies` | 0–8 disposable dependency objects, described below |
| `observers` | 0–16 independent persistence observer configurations |
| `limits` | `cpu_millis` 100–8000, `memory_mb` 128–8192, `pids` 16–512, `world_timeout_seconds` 10–900; integers, not booleans |
| `network` | Exactly `{ "build": "reviewed_dependency_fetch_only", "runtime": "internal_only" }`; policy declaration, not enforced networking yet |
| `reset` | Exactly `fresh_environment_per_world`; must be demonstrated by future live execution |

A project contains `id`, `root`, `language` (`java` or `python`), `image`, `build`,
`test`, `service`. Root/language must match discovery on both revisions. Java
matches Maven/Gradle metadata; Python matches pyproject/setup/dependency metadata.
A language/build signal does not imply the application builds successfully.
Multiple root/language selections are supported; duplicate selections are not.

`build` and `test` are arrays of up to eight command objects. Tests must be
nonempty; build may be empty for interpreted applications. A command has only
`argv` (1–64 bounded strings) and `timeout_seconds` (1–900). Supported executable
names are `mvn`, `./mvnw`, `gradle`, `./gradlew`, `java`, `python`, `python3`.
There is no shell string or implicit interpolation. This is a bounded initial
configuration vocabulary, not a claim to support every Java/Python toolchain.

`service` is null for a library/test-only project, or contains `start` (one command),
`port` (1–65535), `health`, `environment_bindings`. Health has `path` (an internal
absolute HTTP path, not a URL), `status` (200–299), `timeout_seconds` (1–120).
Environment bindings have `variable` (uppercase variable name), `dependency`
(existing dependency id), `field` (host, port, database, username or
`ephemeral_password`). Values are references to disposable runtime data, never
host credentials or inherited environment values. No arbitrary environment map,
mounts, host paths, container options or external health URL is accepted.

A dependency contains `id`, `kind` (`postgres` or `redis`), `image`, `port` and
`seed_files` (0–16 distinct repository-relative paths). File existence, exact
contents and initialization isolation must be checked against admitted source
archives by the future executor. Seed files remain untrusted project code.
Unsupported services require an explicit future capability, not a pass-through
Docker/Compose configuration.

An observer contains `id`, `kind` (exactly `postgres_read_only_snapshot`),
`dependency` (an existing postgres dependency), `tables` (1–16 distinct identifier
names) and `row_limit` (1–10000). There is no model-provided SQL or expected value.
A table allowlist alone does not establish business correctness. The executor
must separately verify read-only database access, deterministic ordering, row-limit
completeness and state capture. Truncation must become inconclusive, not passing.
No observer is required for a stateless configuration; an absent observer cannot
support persistence claims. Redis observation is not implemented by this schema.

## Review and execution boundary

The manifest has no expected failure, experiment sequence, diagnosis, repair
answer, business verdict or healthy-source content. Business expectations belong
to a separate approved contract. Rejected fields protect structure, not semantic
honesty: a command or seed file could encode a prepared scenario. Reviewers must
check that adapters describe infrastructure and do not smuggle in defect-specific
answers. The model must not author executable configuration as trusted policy.

Even a valid `argv` can run arbitrary code: `python -c`, Maven/Gradle plugins,
repository wrappers and install hooks are executable. This validator never runs
any of them and does not certify them safe. Do not put secrets in arguments;
configuration review outputs contain the declared arguments. Future admission
must bind approved commands/images/network policy to the exact source and manifest
hashes and execute only in restricted containers, without Wheel source, host home,
Docker socket, GitHub credentials or Meta credentials. Disposable password bindings
must be created by the executor, never borrowed from the host.

No paid-call workflow consumes this configuration. Historical PetClinic prompts,
fixtures, validator, pilot receipts and negative evaluation are unchanged.

## Validation and next gate

Tests exercise the same contract with unrelated Java and Python layouts, changed
discovery hashes, absent roots, mutable images, traversal, shell entry programs,
resource bounds, external health paths, literal environment fields, unknown
answer fields, duplicate/unresolved dependencies, observer SQL and mandatory tests.
Accepted Python arguments remain explicitly unapproved, and validated results do
not mutate caller input. Existing archive/audit tests continue to pass.

Next: review a trusted image/command/network policy and implement the generic
isolated executor. Validate healthy Java and Python applications and fresh-reset,
observer-access and failure controls in live containers before any new Meta
investigation or repair claim. A configuration-valid result cannot skip that gate.
