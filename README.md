# Codex Wheel — Meta Hackathon 2026

**Verified milestone:** refund and inventory investigation/verification/bounded restoration are integrated through PR #36. Post-merge master baseline and inventory checks passed at `bbd23f1f07d65db7cb7e4f329a9db60af721f81b`. See [two-domain evidence and onboarding](docs/TWO_DOMAIN_DELIVERY.md) for actual results, report viewing and remaining evaluation gates.

Codex Wheel uses **Meta's Model API and `muse-spark-1.3`** to read source/diffs, propose constrained behavioral experiments, select a support-agent refund tool, and produce real post-tool responses. An independent ledger oracle verifies the resulting business effects.

**Verified Meta use:** [G6 Actions 40881599825](https://github.com/PrasathJaga/codex-wheel/actions/runs/40881599825) recorded **18 genuine investigator calls and 52 genuine support-agent calls**. All 70 archived responses identify `muse-spark-1.3` and include provider IDs and usage. The client points to `https://api.meta.ai/v1`. See [META_MODEL_USAGE.md](docs/META_MODEL_USAGE.md) for roles, source links and evidence.

**Analysis and replay are different phases.** Analysis uses genuine Meta inference to choose and freeze an experiment. Default replay reuses that saved plan with zero new inference to check reproducibility. Recorded model messages remain labeled as recorded; replay is not presented as fresh model execution.

The demonstrated domain is a **synthetic full-order refund workflow** with two disclosed seeded defects. G6 verified three paired executions per frozen plan and benign/no-fault controls; it does not measure independent investigator resampling or general bug-finding superiority. See [G6_REPEATABILITY.md](docs/G6_REPEATABILITY.md), [REPLAY_AND_INTAKE.md](docs/REPLAY_AND_INTAKE.md) and [NEXT_STEPS.md](docs/NEXT_STEPS.md) for exact scope and remaining work.

## Source history

Read [CONTRIBUTIONS.md](CONTRIBUTIONS.md) for the distinction between pre-hackathon Codex Wheel source and the new hackathon implementation. The previous Python analysis/indexing ZIP is **not included** in this repository.

## Run Java tests

Requires Java 21 and Maven 3.9+:

```bash
cd services/refund-api-java
mvn test
```

Start the local synthetic API (keep the evaluator token private):

```bash
export WHEEL_EVALUATOR_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
mvn spring-boot:run
```

## Run Python tests

Requires Python 3.11+:

```bash
cd services/support-agent-python
python -m pip install -e '.[test]'
pytest -q
```

## Optional live cross-language verification

With the Java API running and the same private evaluator token exported:

```bash
cd services/support-agent-python
WHEEL_TEST_LIVE=1 pytest -q tests/test_live_integration.py
```

This live test asserts the refund ledger delta; it is skipped in the default unit-test suite. CI runs Java/Python unit tests, live Java/Python integration and a manual counterfactual matrix. Paid G4/G5/G6 workflows are separately bounded.

No real payment system, customer orders or money are involved. The fixture optionally uses a forced append ledger with graceful-restart recovery. The evaluator endpoint is token-protected. Earlier runs use trusted same-host processes; G6 adds constrained containers, with the limits documented above.

## Next engineering gates

The known seeded M1 case has completed a fresh end-to-end cycle: five Meta requests, 24 fresh execution worlds, an evidence-referenced diagnosis, a bounded healthy-baseline restoration, and a GitHub result comment. This demonstrates integration under the tested conditions. Independent unfamiliar-change evaluation, a comparable source-aware conventional baseline, and external developer onboarding remain unverified. See [CURRENT_WORKFLOW.md](docs/CURRENT_WORKFLOW.md) for receipts, limits and the next evaluation gates.

## Baseline CI events

Baseline verification runs on pull requests targeting `master`, pushes to `master` (including merges), and manual dispatch. It does not run on every feature-branch push. These baseline tests are separate from the bounded genuine Meta workflows.
