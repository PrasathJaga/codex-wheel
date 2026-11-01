# Offline consumption of reviewed dependency bundles

This follows the stateless HTTP lifecycle (PR49) and hash-pinned public file
acquisition (PR50). It connects **verified artifact bytes** to the existing offline
Java/Python build/test executor. It adds no dependency resolver, database lifecycle,
service dependency installation, business verifier, Meta experiment or repair.

## Admission and operation

Pass `dependency` to `isolated_executor.run_pair`, containing exactly `archive`
(bundle bytes), `lock` and `acquisition_policy`. The execution policy uses
`schema=wheel-dependency-execution-policy-v1`, retains the original offline fields,
and adds `dependency_lock_sha256` and `dependency_bundle_sha256`. The original
no-bundle policy and default mounts are unchanged; they cannot silently accept
new dependency input.

Before Docker starts, admission recomputes source discovery, validates the shared
manifest and both policies, binds the lock to that exact discovery, authenticates
the bundle hash, and checks its complete regular-file inventory against the lock.
Every file must match its length/hash, with no additional/missing entries. Package
archives remain opaque data on the host. Reconstructing the safe regular-file
bundle does not import Python, run pip/Maven or unpack JAR/wheel payloads on host.
Hash agreement identifies bytes; it does not prove publisher safety or completeness.

The executor creates a fresh separate dependency volume for each world, extracts
the verified regular-file bundle non-root, and mounts it read-only at
`/dependencies` in build/test containers. The original external source stays in
its own work volume and retains its source identity. Dependencies are not inserted
into the source inventory or allowed to overwrite source. Both volumes are removed
with container cleanup; errors remain execution failures. Only admitted source and
bundle archives enter extraction containers, never Wheel source or credentials.
The new mount is included in pre-execution isolation inspection. No network is
added and Docker still cannot pull images during project execution.

CLI (all three bundle-related arguments must be supplied together):

```bash
python -m preflight.isolated_executor \
  --baseline /path/base.tar.gz --candidate /path/head.tar.gz \
  --source /path/source.json --manifest /path/manifest.json \
  --policy /path/trusted-dependency-execution-policy.json \
  --dependency-bundle /path/dependencies.tar.gz \
  --dependency-lock /path/lock.json \
  --acquisition-policy /path/trusted-acquisition-policy.json \
  --output /tmp/new-execution --repetitions 2
```

The trusted caller must supply review policies independently of project/model
output. Reusing an old acquisition-control lock with unrelated discovery is
rejected. Deliberately acquiring the same public files for a newly authored
control requires a new lock commitment bound to its actual source pair. Existing
historical acquisition receipts remain unchanged.

## Package use and limits

The manifest's reviewed build commands decide how to consume bytes inside the
sandbox. For example, pip can install an explicitly locked wheel with `--no-index`
and `--no-deps` into `/work/.deps`; tests explicitly include that location. The
consumer does not automatically import or install anything. A wheel may contain
executable/native code, which belongs only inside the reviewed sandbox. No
arbitrary host resolver, hook or installation is added.

Java can load a reviewed library JAR from `/dependencies/maven/repository/...`.
This **does not** make a Maven plugin/dependency graph available. A read-only
artifact volume is not a complete writable Maven cache. Network-required builds,
missing transitive dependencies, incompatible wheels and missing build plugins
must fail visibly; do not label their dependency closure verified. Runtime reports
retain `dependency_closure_verified=false` and `business_behavior_verified=false`.
They include bundle/lock commitments alongside existing world/check evidence.
Services and database dependencies remain rejected by this executor.

## Controls and next work

The unpaid CI harness uses the predeclared public packaging 24.2 wheel and JUnit
4.13.2 JAR from PR50. It explicitly labels new source pairs as authored controls,
rebinds their locks to actual discovery, acquires the same exact files, then runs:

- Python: offline wheel installation into the work volume, import/version/behavior
  checks, and a read-only dependency-write check.
- Java: class loading of `org.junit.Test` from the reviewed JAR, checks of its
  code-source path and read-only dependency volume.
- Two paired repetitions per language with fresh volumes, followed by replay of
  the original offline healthy/candidate-failure/invalid-baseline controls.

Control runtime image tags resolve to recorded RepoDigests on the trusted CI host,
as in PR48. This is authored capability validation, not unfamiliar-project transfer,
independent investigation, complete JUnit-suite execution or an AI benefit claim.
The local workspace has no Docker; live claims require inspecting CI artifacts.

Next: independent database lifecycle/observer support and complete reviewed
framework dependency environments, before generic behavioral investigation. The
original unsuccessful PetClinic pilot is not modified, relabeled or resampled.
