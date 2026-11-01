# Disposable Postgres service lifecycle

This extends the shared Java/Python manifest and service executor to one HTTP
service with one disposable Postgres dependency. It adds independent state
observation, not behavioral investigation or a business verdict. Generic service
startup was already added in PR49 and reviewed offline dependency consumption in
PR50–51; this increment does not replace those capabilities or the failed pilot.

## Admission and use

Use `preflight.service_executor` with the existing source/manifest inputs and
`--postgres`. The separately trusted policy uses schema
`wheel-postgres-service-policy-v1`; other fields remain manifest_sha256,
allowed_images, max_repetitions and total_timeout_seconds. Source discovery is
recomputed from authenticated archives and bound to the manifest as before.
The policy must be supplied by the trusted operator, not by the project/model.

Exactly one declared Postgres dependency on port 5432 and at least one
postgres_read_only_snapshot observer are required. Image digests must be in the
trusted policy. Repository wrappers and simultaneous dependency-bundle consumption
are not supported by this increment. The old stateless and offline paths remain
unchanged by default. Unknown capabilities remain rejected before execution.

Seed files are reviewed repository-relative SQL files from the authenticated
revision (at most 60,000 bytes each, UTF-8, no NUL). They execute only inside the
disposable database under its initialization administrator; they are untrusted
project code requiring explicit review, never a model-supplied oracle. The source
archive, source root, seed hashes and manifest bind the exact contents. Project SQL
must not be allowed to approve its own policy or encode a desired finding.

## Lifecycle and isolation

Build/tests retain offline isolation. After they pass, a fresh internal network
and Postgres container are created for each revision/trial. Database storage is
fresh tmpfs, not shared across worlds. The approved image must support the
standard Postgres entrypoint, psql/pg_isready and UID/GID 999. Live controls acquire
Postgres 17 on the trusted host, resolve and record its immutable RepoDigest, and
never pull from application containers. Control tags are not fixed production pins.

The database has read-only root, dropped capabilities, no host mounts or published
ports, limited memory/CPU/processes and bounded writable tmpfs. Container settings
and private internal-network endpoint are checked. Database startup is gated on
TCP readiness, avoiding the entrypoint's temporary Unix-socket initialization
server. Fresh random admin, application and observer passwords are generated per
world; only application bindings go to the service. No Wheel source, host home,
project/GitHub/Meta credentials or Docker socket enters a project container.

The control database uses password authentication over the isolated internal
network, not TLS; all credentials are disposable and have no production access.
The initial administrator remains inside the database/trusted controller. The app
role gets SELECT/INSERT/UPDATE/DELETE on initialized tables and sequence usage,
not schema ownership or migration privileges. Migrations requiring additional
privileges need a separately reviewed capability. Dependency configuration alone
does not imply compatibility with arbitrary database applications.

The observer role is separately created after seeding, receives SELECT only on
approved public tables, and is checked for elevated role, inherited role, write
and schema-creation privileges. A real write attempt must fail. Ordinary tables
without row-level security are supported; views, foreign tables and RLS tables are
rejected rather than treated as complete evidence. These checks do not certify
arbitrary hostile seed SQL or container security; seed/image policy review remains
required.

## Independent observations and failures

Three observations are recorded: before application startup, after health polling,
and after confirmed service shutdown. All configured tables in one snapshot are
read through the observer in a single repeatable-read, read-only transaction;
transaction settings are queried and checked. Rows are canonically ordered and
state hashes retained. Queries use validated table identifiers, not model SQL.
Read row_limit+1 to detect overflow: incomplete evidence is an execution error,
never a successful truncated snapshot. Output/operation/world limits still apply.

The executor records state; it does not assert that a particular row count or
change is correct business behavior. A healthy HTTP response alone cannot provide
that conclusion. Initial-state hashes permit checking fresh reset under declared
controls; nondeterministic seeds or intended seed changes need explicit treatment,
not automatic relabeling. Crashes or observation errors can prevent later snapshots;
recorded earlier snapshots remain evidence, and missing final state is not invented.

Application shutdown, log collection and container/network/volume cleanup use the
existing failure-preserving path. Database logs redact generated passwords. Readiness
and observer failures retain execution_error; candidate startup failures remain
candidate_lifecycle_failed. No repair, fallback seed, skipped checks or paid retries
are used to manufacture a passing outcome. The cleanup path removes the disposable
database as well as the service, including after observer failure.

## Validation gate

Unit tests cover trusted policy binding, unsupported topology/images/ports, seed
limits, separate credential bindings/redaction, snapshot transaction semantics and
row-overflow rejection. The dedicated live workflow runs authored Python and Java
HTTP services that write to Postgres using limited app roles. The controller then
observes those writes independently, with initial/after-health/after-stop evidence.
Healthy runs repeat both revisions with fresh databases; candidate startup failures
are retained for both languages. A row-limit control must fail explicitly.
The tiny wire-protocol clients in these fixtures are test plumbing, not production
drivers or a new investigator action interface.

No API keys or paid calls are used. Local Docker is unavailable; unit tests are
not live evidence. The workflow artifacts must establish runtime results. These
are authored runtime controls, not unfamiliar discovery, conventional superiority,
verified repair or universal Java/Python compatibility. The next step is connecting
reviewed generic interface/expectation inputs and complete bounded investigator
tools while retaining the original negative PetClinic evaluation.
