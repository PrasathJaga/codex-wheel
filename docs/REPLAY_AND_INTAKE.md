# Portable replay and pinned source intake

Status: runtime-verified and merged in PR #9 as `de85302d434c8e4ba45f7d3de8d9d3a08098f907`. The merge regression was running at this evidence refresh; source-code regressions and clean-runner replay had passed. Base is merged G6 master `b08c592fd90a152f9036793cc6043f70a088e75c` with master CI 40885686205 passed. This is the next original hackathon deliverable; the conditional stretch plan remains inactive.

## What is supported

The new `wheel.replay` path consumes G6's accepted plans, source snapshots, authorization fixtures and frozen support-agent intent. It never asks an investigator to choose another experiment. Default execution replays only the actual Python wrapper, fault gateway, Java service, protected ledger assertions and graceful restart. It emits `model_reply: null` and zero new model calls. Original model messages remain clearly recorded in the preserved origin evidence. An explicit `--live-continuations` option can request fresh post-tool responses, with a 48-call cap; the no-secret workflow does not enable it.

`wheel.intake` reads full pinned base/candidate Git SHAs without switching the worktree. It requires exactly one changed supported Java domain/Python client file and an unchanged peer, and rejects changed producer/build inputs. Admission is an exact source-byte allowlist derived from the trusted runner's already-reviewed M1/M2/B1/B2 fixtures. A commit hash is provenance, not permission to build arbitrary code. New source bytes require a separately reviewed policy change. This is independently pinned **reviewed-fixture** intake, not generic developer-repository onboarding or the optional adapter stretch project.

The Actions demonstration creates actual local synthetic commits from saved G6 source bytes in an explicit preparation step, supplies those revision pairs to the packaging interface, and exports their Git history. They are disclosed as synthetic fixture commits, not external developer PRs or new blind cases. Their fixed fixture identity/timestamp makes commit IDs reproducible; it does not represent real developer authorship or actual creation time. Both the inspection CLI and packaging interface accept caller-supplied full commit pairs satisfying the same reviewed policy. Packaging requires the four-case inventory; it validates those inputs before Docker/builds and uses their exact commits in the exported source bundle.

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

# Optional caller-supplied pairs; otherwise pack creates disclosed synthetic pins.
python -m wheel.replay pack --evidence /saved/g6 \
  --expected-plan-sha256 EXPECTED_G6_PLAN_HASH --output replay-bundle \
  --revision-pairs /reviewed/revision-pairs.json --source-repo /reviewed/repo

python -m wheel.replay verify --bundle replay-bundle \
  --expected-manifest-sha256 TRUSTED_EXPECTED_MANIFEST_HASH

python -m wheel.replay run --bundle replay-bundle \
  --expected-manifest-sha256 TRUSTED_EXPECTED_MANIFEST_HASH --output replay-results
```

The revision-pair JSON has exactly `M1`, `M2`, `B1`, `B2` keys. Each value contains `base`, `candidate` (full 40-character commit SHAs) and `changed_side` (`java` or `python`). Provided source is still limited to the exact reviewed fixture bytes; author/origin is not independently certified.

Optional fresh continuations also require the OpenAI-compatible Python SDK and `MODEL_API_KEY`. That path is implemented but the default zero-inference workflow does not verify fresh Meta continuation behavior.

The dedicated Actions workflow supplies these steps without requiring laptop commands. Its package job has `actions: read` to download the identified G6 artifact. The clean replay job starts on another runner and receives only the bundle, pinned code and trusted manifest-hash output. No Meta secret is provided. Both raw bundle and replay evidence have 90-day artifact retention; this is finite retention, not permanent archiving.

## Trust and limitations

- Hashes prove consistency with an independently trusted expected root, not author identity or correctness. Do not derive the authorization root solely from an untrusted sidecar.
- The same trusted host/kernel and producer-owned synthetic ledger limits remain. Host-side Maven builds use only already-reviewed synthetic source. Containers do not establish arbitrary hostile-source safety.
- Portable replay is scoped to compatible Linux/Docker architecture and the exact runner commit; it is not cross-platform or cross-language portability.
- Partial refunds remain offline scope counterexamples, not runtime support. Benign investigator abstentions/inherited stress plans remain disclosed in preserved evidence.
- New investigator selection, independent selection reliability, C0/C2/C4 comparison, withheld cases, demo and final submission remain subsequent work. Replay alone does not establish model superiority.

## Validation status

Local offline tests cover pinned commit resolution, reviewed admission, build/peer rejection, Git bundle import, manifest/sidecar/file tampering, fixture/seed/policy validation, unsafe paths/symlinks and absence of default inference. Tests with fake images/JARs or a mocked world are explicitly offline and never counted as container/model evidence. The archived actual G6 plans also passed the new input validation locally.

The clean Actions packaging/replay workflow must pass and its artifacts must be inspected before claiming runtime replay success. The inspected successful executions are recorded next.


## Inspected clean-runner executions

### Initial generated-pin packaging path

Executable revision `5322d36f0bbc89427c4aa55e9fdb8a509a7be5df`, Actions [40973653126](https://github.com/PrasathJaga/codex-wheel/actions/runs/40973653126), passed. The package and replay ran on separate GitHub runners. All 48 worlds completed with zero investigator calls and zero fresh support-agent calls; every replay `model_reply` was null. M1/M2 selected plans each reproduced baseline [1,1,1] versus candidate [2,2,2] effects. Benign/no-fault controls retained one effect. Recorded replay wall time was approximately 452.5 seconds; no speedup/general performance claim is inferred.

- Bundle artifact: 12941666980; ZIP SHA-256 `1dc723e5223e2613fffd7fca71eda091a145237876f049c86dbf292b96239b97`.
- Manifest SHA-256: `94f53492f03302425a966285f41fe873c90406e0bf87143e6930799ca00f12b0`.
- Replay evidence artifact: 12942306064; ZIP SHA-256 `adf9f2992ec654a705113f4d89af0fa9aae097a384e662cb7003957435f666b9`.

### Caller-supplied reviewed commit-pair path

Executable revision `d9801353f28df4a35d8d56e4ed9757628e6f45b1`, Actions [40974431811](https://github.com/PrasathJaga/codex-wheel/actions/runs/40974431811), passed. A separate preparation step supplied four disclosed synthetic pinned commit pairs to packaging. Their exact SHAs were admitted, exported and revalidated on another clean runner before runtime loading. This exercises caller-supplied intake; it does not claim new external developer PRs or arbitrary code admission.

| Plan group | Baseline effects in three trials | Candidate effects in three trials | Actual outcome |
| --- | --- | --- | --- |
| M1 selected, drop | 1 / 1 / 1 | 2 / 2 / 2 | reproduced_regression |
| M2 selected, 502 | 1 / 1 / 1 | 2 / 2 / 2 | reproduced_regression |
| B1/B2 stress controls | 1 / 1 / 1 each | 1 / 1 / 1 each | not_reproduced each |
| Four no-fault controls | 1 / 1 / 1 each | 1 / 1 / 1 each | not_reproduced each |

All 48 worlds completed. Every ledger row count was independently checked against its recorded effects; fresh/reset and graceful restart checks passed. All ten confinement probes passed; 193 mandatory integrity checkpoints were recorded. Default replay made zero investigator and zero fresh support-agent calls, with null fresh model replies. This does not alter the genuine Meta use in the original analysis run; see META_MODEL_USAGE.md.

- Package artifact: [12942032169](https://github.com/PrasathJaga/codex-wheel/actions/runs/40974431811/artifacts/12942032169).
- Package ZIP SHA-256: `1088d78ed52c20d7bf1e4a8a5c0fbd30a3f13ed1009bbdbadea8a34b1b3f17f7`.
- Expected manifest SHA-256: `614c53b29dbc03640d261dca94dce5414bcc9105f59f93b61a99207bcc01ede9`.
- Replay evidence artifact: [12941334841](https://github.com/PrasathJaga/codex-wheel/actions/runs/40974431811/artifacts/12941334841).
- Replay evidence ZIP SHA-256: `52defefb02fe3ff565c88455d25b29d1d5768c2a4060ab0cc29a05b888525397`.
- Replay wall time: approximately 683.7 seconds, recorded for this specific runner/run.
- Actions offline tests: 61 passed, one live-only skip, 14 subtests passed. Full code-revision PR/push regressions 40974436568 and 40974431820 passed.

Independent inspection recomputed both bundle ZIP/manifest hashes and all 121 listed files per bundle (including image archives and JARs), matched each expected manifest root to its trusted package-job output, and checked pinned source pairs through Git. Both replay evidence ZIPs, plan identities, completed world inventories, ledger row counts, verdicts and zero-new-inference labels were inspected. These are two replays of the same eight frozen experiments, not 96 independently discovered cases. No new successful Meta inference is attributed to either replay.

The latest bundle preserves raw original G6 evidence plus the replay's immutable runtime/source closure for the configured 90-day artifact retention. Other historical G4/G5 evidence still needs the broader archival pass. Optional fresh replay continuations remain implemented but are not runtime-verified by these zero-key workflows.
