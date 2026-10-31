# External repository preflight

This first work package adds an isolated, unpaid baseline build/startup check for
Spring PetClinic REST at `e1987d2b4715b30f8b97050b3a399fdcadf92cb3`.
It does not establish detection, business-contract validity, repair, or production usefulness.

## Mandatory non-exposure boundary

The external job runs on a separate hosted runner and never checks out Wheel.
It receives no repository/model secrets and has empty GitHub token permissions.
Only the public upstream archive is mounted into its build container, read-only.
Upstream extraction, Maven plugins, tests, and service code execute inside containers.
No host home, Wheel directory, Docker socket, or evaluator credentials are mounted.
Build dependency download has internet access; the container contains no private
inputs to disclose. This is not a Maven-domain egress allowlist. Runtime and
health probes have no outbound network. The probe shares only the service's
network namespace, never its filesystem or Docker socket.

Images are pulled, resolved to immutable repository digests, recorded, and then
executed by digest. Builds run without Linux capabilities, with no-new-privileges,
read-only root, resource limits, and disposable work/tmp storage. The build is
non-root. Rootless/user-namespace VM isolation is not claimed; host/kernel and
GitHub's runner platform remain trusted. Do not extend this admission to arbitrary
hostile repositories based solely on this preflight.

Raw upstream logs are untrusted evidence. They are redirected to fixed host files,
not printed as GitHub workflow commands. Artifact upload runs after containers stop;
it publishes only those fixed logs and trusted metadata, never paths supplied by
upstream. There is no upstream issue, PR, callback, credential, or Wheel source transfer.
Existing public visibility of Wheel is independent of this integration.

## Execution and interpretation

The workflow runs on changes to these preflight files and manually. The policy
job checks the trusted workflow; a separate runner downloads only upstream source.
Maven `verify` runs with unchanged upstream tests. Sonar publishing is omitted;
no test, coverage gate, or build plugin is disabled. A build failure stops startup.
Startup is checked twice using fresh containers and seeded in-memory H2, recording
health and the owners API response. Identical owners responses support reset
repeatability only; they are not independent database verification.

Success means build/test execution and repeated startup probes succeeded.
Failure remains a baseline/preflight failure, not a behavioral regression finding.
Timeouts and logs remain visible in the artifact. No automatic fallback, candidate
mutation or paid inference occurs. The business expectation (profile updates preserve
owner/visit relationships) must pass an independent committed-state check in the
next work package before any candidate evaluation.

The initial build image follows the upstream CI's documented Java 17 choice.
Record and preserve any incompatibility rather than changing upstream dependencies.
The local authoring environment has no Docker/Maven; GitHub execution is required
to validate runtime behavior. Until a run succeeds, runtime verification is pending.
