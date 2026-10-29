# Codex Wheel — Meta Hackathon 2026

**Current master evidence:** G1 live Java/Python, the manual G2/G3 matrix, genuine Meta support-agent/preflight and bounded source-reading G5 investigator are demonstrated in linked Actions runs. PR #7 merged as `ec55072fede610c26265e9660828f9530cf1a4f6`.

Codex Wheel uses a Meta-powered investigator to choose source-grounded experiments and independently validates committed business effects in a **synthetic refund workflow**. G5 covers two disclosed seeded cases, one selected paired trial each. It does not establish general bug-finding accuracy or superiority over deterministic methods.

The G6 branch adds repeated live-plan trials, benign/no-fault controls, strict parity and constrained Docker execution. See [G6_REPEATABILITY.md](docs/G6_REPEATABILITY.md) for protocol, evidence status and limitations. See [NEXT_STEPS.md](docs/NEXT_STEPS.md) for the remaining replay/evaluation/demo work.

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

G0: provenance and pinned commits. G1: real Java HTTP and Python tool integration with a protected one-effect assertion. G2: post-commit fault gateway. G3: manually frozen M1/M2 experiments and oracle. G4–G7: actual Meta agent/investigator, freeze-before-comparison, controlled trials, honest baselines, replay evidence and demo.
