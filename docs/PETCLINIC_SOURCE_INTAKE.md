# Complete source intake and separate candidate build

This extends the pre-evaluation adapter with actual archive collection and a
separate build path. The live case is deliberately an unchanged-source control,
not a fresh regression. Both sides use the pinned public upstream archive. There
are no candidate mutations, paid calls or new discovery/repair claims.

## Source authority and collection

The raw baseline archive SHA-256 is anchored to PR #40's authenticated artifact
13051121050 from run 41224056142. A changed archive fails closed, even if GitHub
only changes archive packaging. The configured candidate digest is a trusted,
reviewed input; model-provided hashes are not authority. Archive root names are
structural checks, not proof that contents belong to a Git commit.

Before any upstream build, the host collector verifies the raw hashes and reads
the COMPLETE archives. It limits compressed bytes, expanded bytes, entries and
per-file size; rejects links, special/sparse entries, duplicate paths, traversal,
unexpected roots and file/directory collisions. It never extracts source onto the
host or executes source. It creates full path/content-SHA-256 maps, applies the
existing allowed-edit boundary, and reconstructs fresh regular-file-only archives
with normalized ownership, mode and time. Only these admitted archives are mounted
into build containers. File modes are normalized to 0644; this interface does not
support candidate changes that depend on executable source modes.

The source maps and original/normalized digests are preserved as evidence.
Unsupported additions, deletions, build/test changes or malformed archives stop
the workflow before build. The collector cannot establish that an incomplete
candidate archive is complete by assertion: its full file set must match the
known complete baseline archive, and all differences must be in allowed paths.

## Separate builds and execution

Baseline and candidate are built in different disposable volumes/containers using
the same resolved Maven image and unchanged Maven verification command. They do
not share build output. Build timestamps can differ, so byte-identical JARs are not
an acceptance requirement. Public dependency acquisition has internet access and
contains no Wheel source or project credentials. Runtime remains on the private
internal network, with no published ports and no Docker/host filesystem mounts.

Each source build then executes both frozen public plans against fresh PostgreSQL:
four worlds total, two plans per source variant. The SQL oracle checks every action
and post-service-stop state; all seeds must agree. This demonstrates the intake
path on an unchanged pair. It does not prove behavior on an unfamiliar changed pair.

## Scope and freeze status

Automatic arbitrary-PR admission, external fork acquisition, candidate mutation,
model selection and repair remain disabled. Future cases must provide reviewed
candidate bytes/digests via a controlled acquisition step; do not add arbitrary
URLs or repository tokens to the external runner. The path restriction is narrow
and does not imply generic Java support or a hostile-code sandbox guarantee.

The pre-evaluation lock is refreshed at a new reviewed revision to include source
intake. No held-out candidate has been prepared or evaluated, so no evaluation
results are relabeled. Pin the merged verified revision before fresh cases. Any
subsequent evaluator/interface changes must be versioned and reported separately.

Local tests cover archive attacks, budgets, protected paths, failure preservation
and admission-before-build ordering. Live GitHub verification remains necessary;
the authoring environment has no Docker/Maven. Existing protected refund/inventory
sources and historical evidence are unchanged.
