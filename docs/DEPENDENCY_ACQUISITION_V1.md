# Reviewed dependency artifact acquisition v1

This increment acquires hash-pinned public dependency files as **data**. It does
not install dependencies, resolve a dependency graph, execute build hooks, assemble
a complete Maven cache, or connect a database. It is independent of the pending
HTTP-service PR and leaves that executor and all frozen evaluation results intact.

## Research and design decision

Primary documentation consulted 1 November 2026:

- https://pip.pypa.io/en/stable/topics/secure-installs/ explains hash-checking and
  binary-only installation; do not run source-distribution build code on the host.
- https://pip.pypa.io/en/stable/cli/pip_download/ describes download directories
  for later offline installation. This module performs no pip invocation.
- https://maven.apache.org/plugins-archives/maven-dependency-plugin-3.11.0/go-offline-mojo.html
  covers project, plugin and report dependency resolution. A library JAR alone
  cannot establish that an unfamiliar Maven build has a complete offline closure.

Decision: separate reviewed file acquisition from all project execution. Source
build hooks, Maven extensions, plugins, setup.py and installer code belong only in
an admitted sandbox. Never run a project resolver on the trusted host merely to
populate a cache, and never give a project build general network access as a
shortcut. Actual sandbox consumption/closure validation is a later integration.

## Interface and trust

`preflight.dependency_bundle` accepts:

- A closed lock with `schema=wheel-dependency-lock-v1`, `discovery_sha256`,
  `purpose` (`execution_dependencies` or `authored_acquisition_control`) and
  `artifacts`.
- Each artifact has `kind` (`python_wheel` or `maven_artifact`), exact `url`,
  `sha256`, `size_bytes` and `destination`.
- A separately trusted policy with
  `schema=wheel-dependency-acquisition-policy-v1`, `lock_sha256`, `allowed_urls`,
  `total_timeout_seconds` (1–600), `artifact_timeout_seconds` (1–120).

The caller must bind the discovery hash to its actual reviewed source pair and
keep the policy outside project/model control. This downloader verifies that the
lock matches the policy, but it does not authenticate the discovery's provenance
or implement a cryptographic approval service. A project cannot approve itself.
Artifact hashes assure byte identity, not publisher safety, license compatibility,
package compatibility, or completeness. No dependency choice is inferred by AI.

Only exact HTTPS file URLs on `files.pythonhosted.org` (wheel files) or
`repo.maven.apache.org/maven2/` (JAR/POM files) are supported. No URL credentials,
query/fragment, custom port, percent-encoded path, traversal, redirect, private
registry or arbitrary origin is accepted. Private registries and source builds
need separate reviewed capabilities; this is not every Java/Python package source.

DNS is resolved once. Any nonpublic answer rejects the fetch; the TLS socket
connects to the selected public IP while validating the original hostname/SNI.
No proxy, cookies, client credentials, repository source or Wheel source is sent.
Each artifact runs through a trusted isolated downloader process with a hard
parent deadline, bounded file size and bounded receipt. This is process lifecycle
control, not execution of dependency bytes or an independent security sandbox.
DNS/connection/certificate/content failures are preserved; there is no retry or
fallback to a less restrictive transport.

Budgets: 1–64 files, at most 8 MiB each and 32 MiB aggregate/bundle, aligned with
the existing regular-file archive collector. Wheel destinations use
`python/wheels/<exact filename>`; Maven destinations preserve repository layout
under `maven/repository/`. Duplicate URLs and destinations are rejected. Package
archives are opaque bytes and are not extracted or imported by this component.

```bash
python -m preflight.dependency_bundle \
  --lock /path/reviewed-lock.json --policy /path/trusted-policy.json \
  --output /tmp/new-dependency-result
```

Before each attempt, `result.json` records its commitment and attempted status.
Size/hash mismatch, timeout or access failure stops later fetches. Earlier verified
receipts remain; no success bundle is published on failure. Only after all files
match does `dependencies.tar.gz` become available, with a recorded SHA256. Its
normalized `admitted/` archive is deterministic for the same bytes; input data
never supplies archive ownership, symlinks or modes. Output directory must be new.

`artifacts_verified` means byte acquisition only. `packages_installed=false`,
`project_code_executed=false`, `dependency_closure_verified=false`, `model_requests=0`
remain explicit. Failure is `acquisition_failed`, never an invented passing cache.

## Fixed controls and retained failure

`evaluation/dependency_acquisition_controls_v1.json` precommits one packaging 24.2
wheel and one JUnit 4.13.2 JAR, including URLs, lengths, SHA256, policy, a synthetic
source-discovery context and provenance. These were deliberately selected download
controls, not unfamiliar investigation cases or evidence of complete dependency
resolution. The Python SHA256 comes from PyPI's release JSON. The Maven SHA256 was
computed from HTTPS bytes and compared with the publisher's SHA1 file for byte
agreement; its `.sha256` endpoint returned 404. That provenance is retained, not
presented as an independently authenticated publisher SHA256 signature.

The first direct local acquisition failed on artifact-host DNS resolution and
produced no bundle. Its receipt is committed as
`evaluation/dependency_acquisition_local_failure_v1.json`. We did not loosen the
policy or use a proxy fallback. The GitHub acquisition workflow runs the **same**
fixed controls in its normal runner environment and preserves its own outcome.
Do not erase the local failure if CI succeeds: supported environment requirements
are part of the product boundary.

Offline tests verify deterministic bundles, digest/size mismatch retention,
first-failure stopping, changed locks, unsupported origins and credentials,
traversal, path mismatch, budgets, duplicate artifacts, private DNS rejection and
TLS hostname/IP pinning. The live download workflow needs no API secret, Docker,
package installer, Maven invocation or Meta call. A green unit check alone is not
live acquisition evidence.

Next: verify live acquisition, add sandbox-only bundle consumption with an offline
closure check, and implement disposable database lifecycle/observer controls.
Dependency bundling does not establish business correctness or resolve the failed
Meta investigator evaluation.
