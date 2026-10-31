# Healthy PetClinic committed-state contract

This work package checks the pinned healthy service before any new candidate or
model investigation. Updating the pet's name, birth date and type must preserve
its identity, owner, existing visit records and unrelated state. This is a scoped
data-integrity expectation, not a per-owner authorization or clinical safety claim.

The trusted host verifier is embedded byte-for-byte in the workflow. Tests check
that the reviewed module and embedded code agree. It never executes inside the
external service, and no Wheel checkout is made on the external runner. The service
receives only upstream build output and randomly generated disposable application
database credentials. The build keeps its earlier no-private-input boundary.

Each of two trials creates a fresh PostgreSQL database and internal Docker network.
Neither service nor PostgreSQL publishes a host port. The trusted host
addresses the service through its inspected private bridge address. There is no outbound runtime network, Docker socket or host/Wheel bind mount.
The host/kernel and reviewed database image remain trusted. Internal networking
is a change from the network-none H2 smoke test, required for service/database
communication. It does not provide a general hostile multi-tenant sandbox.

A separate verifier role has SELECT privileges and defaults to read-only
transactions. A write attempt must be rejected. The application receives neither
administrative nor verifier credentials. SQL snapshots use a consistent read-only
transaction over owners, pets, visits and types, independent of API responses.
The application owns its disposable schema for normal upstream initialization;
this oracle does not defend against a malicious database-owning application.

For a seeded pet with visit history, the verifier checks rejected invalid input
and a missing target leave all rows unchanged, then checks a valid update changes
only the three permitted fields. After stopping the service it reads PostgreSQL
again to confirm those committed effects remain. Database-process crash durability
and restart recovery are not tested. Both fresh trials must have identical seeds.

Artifacts retain requests/responses, before/after rows, read-only access proof,
logs and an explicit result. A failing healthy contract is a baseline failure;
timeouts and startup problems are execution errors. There are no candidate
changes, paid model calls, independent discovery claims or repairs in this step.

Local verification covers the oracle's rejection of owner changes, visit loss,
visit reassignment/content corruption, unrelated writes, missing evidence and
HTTP-success-without-effect. Real Docker/PostgreSQL verification requires GitHub
execution because the authoring workspace lacks Docker/Maven.

## Preserved first execution

Run 41221978757 at head 42f55c7def7a36142f2cb55dbae313f488ace93e
built successfully and passed both H2 probes. The first PostgreSQL trial was an
execution error: service readiness timed out before contract requests. Artifact
13050686617 (ZIP SHA-256
542e0ade4d280f2159ddbcc4de3ed5b6a6a506af69b651d67c1387397c66af80)
records the failure. Inspection showed PostgreSQL connected and PetClinic fully
started; the host health probe still timed out, consistent with a transport
problem rather than an application startup failure. The precise loopback failure
mechanism is not established by those logs. The harness now uses the
container's inspected private bridge address, with no published port. This changes
transport only, not upstream source, expectations, validation or oracle. The new
execution must pass independently; the earlier failure is not overwritten.
