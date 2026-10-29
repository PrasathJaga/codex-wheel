# Portable replay and pinned source intake

Status: implemented on `hackathon/g7-replay-intake`; clean-runner runtime evidence pending. Base is merged G6 master `b08c592fd90a152f9036793cc6043f70a088e75c` with master CI 40885686205 passed. This is the next original hackathon deliverable; the conditional stretch plan remains inactive.

## What is supported

The new `wheel.replay` path consumes G6's accepted plans, source snapshots, authorization fixtures and frozen support-agent intent. It never asks an investigator to choose another experiment. Default execution replays only the actual Python wrapper, fault gateway, Java service, protected ledger assertions and graceful restart. It emits `model_reply: null` and zero new model calls. Original model messages remain clearly recorded in the preserved origin evidence. An explicit `--live-continuations` option can request fresh post-tool responses, with a 48-call cap; the no-secret workflow does not enable it.

`wheel.intake` reads full pinned base/candidate Git SHAs without switching the worktree. It requires exactly one changed supported Java domain/Python client file and an unchanged peer, and rejects changed producer/build inputs. Admission is an exact source-byte allowlist derived from the trusted runner's already-reviewed M1/M2/B1/B2 fixtures. A commit hash is provenance, not permission to build arbitrary code. New source bytes require a separately reviewed policy change. This is independently pinned **reviewed-fixture** intake, not generic developer-repository onboarding or the optional adapter stretch project.

The packaging demonstration creates actual local synthetic commits from saved G6 source bytes and exports their Git history. They are disclosed as synthetic fixture commits, not external developer PRs or new blind cases. The CLI also accepts independently supplied commits satisfying the same reviewed policy.

## Package once, replay on a clean runner

1. Verify the caller-supplied original G6 locked-plan SHA-256 before Docker, builds or network. Validate the fixture, intervention, conversation/tool-call identity, source/peer hashes and protected verifier/engine version. G6 appended continuations after locking its initial trace prefix; packaging verifies that original four-selection prefix rather than treating its later full trace as unchanged.
2. Preserve the raw G6 evidence in `origin/`, including failed/recorded outcomes where present. Build the already-reviewed Java variants using the trusted template. Resolve and save runtime image archives and JARs, with immutable IDs and file hashes. Export the pinned source revisions and intake records.
3. Write a new replay manifest containing all original plans, original plan hash, three-trial policy, protected engine hashes, source provenance and an exact file inventory. The expected manifest hash must come from a trusted workflow output or record, separately from the bundle; rewriting a sidecar does not authorize changed input.
4. On a separate clean Linux runner, verify every manifest/file hash, byte count, path, source commit, fixture and peer before `docker load` or execution. Require the exact pinned runner revision. Load the archived images rather than pulling mutable tags, then check actual image IDs and confinement.
5. Run the same eight plans with fresh state, three baseline/candidate pairs each. Report actual outcomes, including mixed results/errors. The original result is not hardcoded as the replay verdict.

The old G6 artifact recorded local image IDs and JAR hashes but did not export its binary images/JARs. Therefore this first conversion reconstructs a runtime once from the original source/plan/seed and records that fact. It does **not** claim byte-identical recovery of the original G6 binaries. Subsequent replay of the new bundle uses its exact archived binaries and images. The first package may resolve dependencies differently; the bundle freezes the resulting closure for later replay.

## Executable interfaces

Use full SHAs, and obtain expected hashes from a trusted run/record. The commands below describe implemented interfaces; runtime verification status is tracked separately below.

```bash
python -m wheel.intake --repo /reviewed/repo --base FULL_BASE_SHA \
  --candidate FULL_CANDIDATE_SHA --changed-side java

python -m wheel.replay pack --evidence /saved/g6 \
  --expected-plan-sha256 EXPECTED_G6_PLAN_HASH --output replay-bundle

python -m wheel.replay verify --bundle replay-bundle \
  --expected-manifest-sha256 TRUSTED_EXPECTED_MANIFEST_HASH

python -m wheel.replay run --bundle replay-bundle \
  --expected-manifest-sha256 TRUSTED_EXPECTED_MANIFEST_HASH --output replay-results
```

The dedicated Actions workflow supplies these steps without requiring laptop commands. Its package job has `actions: read` to download the identified G6 artifact. The clean replay job starts on another runner and receives only the bundle, pinned code and trusted manifest-hash output. No Meta secret is provided. Both raw bundle and replay evidence have 90-day artifact retention; this is finite retention, not permanent archiving.

## Trust and limitations

- Hashes prove consistency with an independently trusted expected root, not author identity or correctness. Do not derive the authorization root solely from an untrusted sidecar.
- The same trusted host/kernel and producer-owned synthetic ledger limits remain. Host-side Maven builds use only already-reviewed synthetic source. Containers do not establish arbitrary hostile-source safety.
- Portable replay is scoped to compatible Linux/Docker architecture and the exact runner commit; it is not cross-platform or cross-language portability.
- Partial refunds remain offline scope counterexamples, not runtime support. Benign investigator abstentions/inherited stress plans remain disclosed in preserved evidence.
- New investigator selection, independent selection reliability, C0/C2/C4 comparison, withheld cases, demo and final submission remain subsequent work. Replay alone does not establish model superiority.

## Validation status

Local offline tests cover pinned commit resolution, reviewed admission, build/peer rejection, Git bundle import, manifest/sidecar/file tampering, fixture/seed/policy validation, unsafe paths/symlinks and absence of default inference. Tests with fake images/JARs or a mocked world are explicitly offline and never counted as container/model evidence. The archived actual G6 plans also passed the new input validation locally.

The clean Actions packaging/replay workflow must pass and its artifacts must be inspected before claiming runtime replay success. No such success is claimed by this initial implementation note.
