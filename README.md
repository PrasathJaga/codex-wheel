# Codex Wheel — Meta Hackathon 2026

**Current code status:** G0/G1 baseline candidate; not an end-to-end v3.2 investigator.

Codex Wheel aims to discover agent-tool/backend behavioral regressions by having a Meta-powered investigator choose source-grounded experiments and by independently validating business effects.

This branch introduces a **synthetic** Java refund API and a **non-agent** Python tool wrapper. It does not yet contain a working Meta investigator, real Meta model calls, fault proxy, M1/M2 mutation comparisons, independent external oracle or reproducible counterfactual verdicts.

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

This live test asserts the refund ledger delta; it is skipped in the default unit-test suite. CI currently runs Java and Python unit tests, **not** the live Java/Python integration test.

No real payment system, customer orders or money are involved. The initial ledger is in memory, and reset on restart. The evaluator inspection endpoint is protected by a token and bound to loopback by default; G2 requires stronger isolation and verified post-commit fault semantics.

## Next engineering gates

G0: provenance and pinned commits. G1: real Java HTTP and Python tool integration with a protected one-effect assertion. G2: post-commit fault gateway. G3: manually frozen M1/M2 experiments and oracle. G4–G7: actual Meta agent/investigator, freeze-before-comparison, controlled trials, honest baselines, replay evidence and demo.
