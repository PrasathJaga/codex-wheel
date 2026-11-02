# Submission copy

## Project name
Codex Wheel

## One-line description
Meta-powered change investigation that reproduces behavioral failures and verifies
committed effects before a developer merges.

## What we built
Codex Wheel connects source-aware investigation to controlled execution and
independent verification. Meta reads the relevant Java/Python source, proposes a
bounded experiment, and explains its results using recorded source and execution
references. The verifier decides whether the observed business expectation holds.

The main demonstration investigates a retry/idempotency interaction: a lost
post-commit response leads an unchanged Python client to retry a refund, while a
changed Java deduplication condition permits a second committed effect. The API
receipt describes a USD20 refund; the ledger contains USD40. Three paired trials
reproduce the difference. A bounded restoration is proposed and checked against
the original experiment and controls.

A reservation example demonstrates a second stateful domain: checkout after
explicit expiry, with persisted order verification and bounded restoration.
Generic Java/Python HTTP controls additionally exercise real model-selected plans
and evidence-linked diagnosis through a shared strict schema.

## Meta's contribution
The model chooses and explains bounded experiments from source, proposes a repair
within declared boundaries, and links diagnosis to specific observations. Real
provider receipts, selected plans and original outcomes are inspectable. Models
cannot create a passing verdict, change approved expectations, execute arbitrary
shell commands or replace independent verification with prose.

## What is newly implemented for the hackathon
The runtime refund and inventory fixtures, Meta investigation/gateway integration,
experiment admission and freeze, execution verification, bounded restoration,
GitHub evidence workflow, financial explanation and report are documented in the
repository contribution ledger. Generic discovery/configuration, restricted
runtime controls and real Meta HTTP integration are additional event-period work.
Pre-event repository-intelligence work is identified separately; it is not
presented as newly built hackathon functionality.

## Evidence-backed results
The refund cycle records five actual Meta requests and 24 fresh worlds. Inventory
investigation/restoration records two distinct requests and retains unchanged JUnit
results. The generic integration records seven requests: two known violating
controls confirmed, one preserving control without an observed violation, and one
preserving control inconclusive after abstention. Original unsuccessful outcomes
remain available. These are integration results on disclosed known examples.

## Scope and future
Healthy repair answers are supplied in the demonstrated restoration tasks. This
is not evidence of general unfamiliar-defect repair or superiority over existing
tests; inventory's existing JUnit suite already caught the defect. Broad automatic
Java/Python environment reproduction and independently prepared evaluation remain
unfinished. No production loss/savings or adoption claim is made.

The future product direction is a pre-production system that understands changes,
reproduces environments, chooses experiments and helps verify repairs. The current
submission demonstrates the executable evidence loop and its supported boundaries.

## Submission fields requiring final owner action
Public video URL: pending upload/access check.
Final submitted repository revision: select after reviewing/merging the delivery PR.
Contributor names: verify actual event contributors; do not infer identities.
Final competition-platform submission: not performed by these files.
