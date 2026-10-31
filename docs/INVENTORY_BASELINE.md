# Inventory adaptation: healthy baseline (Gates 1–3)

This phase adds a second synthetic domain without changing refund execution or investigation. It implements a healthy fixture and tests only. There is no seeded candidate, Meta investigation, generalized intake, discovery claim, repair or financial projection yet.

## Business contract

One SKU (`last-item`), initial stock one, quantity one per reservation. A successful checkout must refer to a committed order backed by an exclusive confirmed reservation belonging to the same buyer. ACTIVE holds plus CONFIRMED allocations cannot exceed stock. Each reservation can back at most one unique order. Confirmation consumes the hold; stock is not replenished after a confirmed order. Cancellation/restocking, payment, multi-SKU, multi-node storage, real customer authentication and arbitrary workloads are out of scope.

| Current state | Operation | Result |
| --- | --- | --- |
| Absent, capacity available | Reserve | ACTIVE hold |
| ACTIVE | Confirm by same buyer | CONFIRMED allocation and one committed order, atomically |
| ACTIVE | Release by same buyer | RELEASED; capacity available |
| ACTIVE | Evaluator expiry event | EXPIRED; capacity available |
| EXPIRED or RELEASED | Confirm | 409; no committed order |
| CONFIRMED | Release or expire | 409; allocation remains committed |
| Any existing ID | Identical reserve | Existing state; never resurrects expired/released IDs |
| CONFIRMED | Identical confirmation/order ID | Original order; no additional event |
| RELEASED or EXPIRED | Same release or same expiry respectively | Existing state; no additional event |

An unknown reservation gives 404; malformed identifiers/SKU give 400; mismatched buyer gives 403; no capacity gives 409. Buyers are explicit fixture labels, not authenticated identities. The ownership check prevents accidental label mixing; it is not production authorization.

## Expiry semantics and concurrency boundaries

`POST /internal/evaluator/trigger-expiry` with a named reservation is an explicit lifecycle event. It does **not** assert that physical time advanced or that a production expiry sweep would run at that instant. Future DSL must call this `TRIGGER_EXPIRY`, not imply clock travel. No sleeps control business ordering.

All Java state transitions are synchronized within one process. Competing reserve/confirm tests check that only one operation wins. The expiry/reallocation sequence is an explicitly ordered lifecycle test, not evidence of an actual in-flight distributed race. Finer scheduling, wall-clock boundaries, multiple nodes and database isolation would need separately modeled interfaces and verification.

## Architecture and persistence

- `services/inventory-api-java`: Spring HTTP API on loopback port 8081, a reservation state machine and atomic order/allocation commits.
- `services/checkout-agent-python`: deterministic public API client; it accepts only a confirmation response matching the requested buyer, reservation and order. It never receives the evaluator key. No agent conversation or model call exists in this phase.
- `checkout_agent/verifier.py`: host-side verifier reconstructs lifecycle from events, checks conservation at every recorded step, reconciles final reservations/orders and matches accepted receipts to allocated orders. Rejection or incomplete evidence raises an error rather than producing a pass.
- Storage: one schema-versioned JSON snapshot with events, reservations and orders. Write and force a temporary file, then atomically replace the snapshot before acknowledging success. A process-wide file lock prevents another store writer. Startup checks schema and allocation consistency, failing closed on corrupt/inconsistent state. Independent event reconciliation is additionally performed by the verifier.

This is local synthetic persistence. Graceful restart is tested; power-loss/filesystem durability, transactional distributed databases and long-running storage limits are not established. The snapshot/event list grows with operations and is intended only for bounded experiments. The host, file system and evaluator remain trusted.

Internal endpoints require `X-Evaluator-Token` matching `WHEEL_INVENTORY_EVALUATOR_TOKEN` (at least 32 UTF-8 bytes). An absent/short configuration disables evaluator access. State inspection and forced expiry are evaluator-only. Do not expose this fixture outside a trusted local test environment.

## Run baseline verification

Java 21 and Maven 3.9+:

```bash
mvn -B -f services/inventory-api-java/pom.xml verify
```

Python 3.11+, no runtime third-party dependencies:

```bash
PYTHONPATH=services/checkout-agent-python python -m unittest discover -s services/checkout-agent-python/tests -v
```

Actual Java HTTP/Python execution (after packaging):

```bash
PYTHONPATH=services/checkout-agent-python \
WHEEL_INVENTORY_LIVE=1 \
WHEEL_INVENTORY_JAR=services/inventory-api-java/target/inventory-api-java-0.1.0-SNAPSHOT.jar \
WHEEL_INVENTORY_OUTPUT=inventory-baseline-evidence \
python -m unittest discover -s services/checkout-agent-python/tests -p test_live_inventory.py -v
```

Each live test starts a fresh Java service on loopback port 18081 with its own temporary state and random evaluator token. Readiness polling uses time solely to wait for startup. Tests compare the protected state response to actual disk bytes parsed as JSON, then verify the event/order records. Outputs contain no evaluator token. Port 18081 must be free; do not run these live tests concurrently on the same host.

CI `inventory-baseline.yml` runs Java tests, Python unit tests and five live cross-language scenarios, preserving evidence and JUnit reports even on failure. Existing `verify.yml` continues unchanged and must pass as well. Default Python discovery skips live tests unless explicitly enabled; a skipped live suite is not live validation.

## Gate and next phase

The JUnit suite deliberately includes the expiry → reallocation → old-checkout-rejection sequence and competing operations. Freeze the baseline implementation/test identities at the accepted commit before preparing any candidate. Do not weaken tests or remove safety checks to manufacture a Meta-only success. If the unchanged tests catch a future mutation, retain that result as useful conventional coverage.

The implementation contains defense-in-depth invariant checks before commit. A future proposed mutation may consequently fail closed with an error instead of overselling. That is a valid result; it must not be removed just to make an impressive demonstration. Candidate selection and whether the consumer or producer changes remain for the next reviewed phase.

Before paid investigation, register exact candidate scope, bounded DSL/sequence length, source admission, baseline/test hashes, conventional source-aware comparison, model request/token/world caps and stop rules. Do not supply the intended event sequence to the investigator and then claim it discovered the sequence. Retain abstentions, test catches and unsuccessful executions.

A second author-prepared fixture would demonstrate adapter breadth only. An independently prepared unfamiliar case, comparative advantage and general behavioral discovery remain separate unverified goals. Inventory impact should initially be reported as stock, valid allocations and committed/accepted orders; no dollar loss is inferred.
