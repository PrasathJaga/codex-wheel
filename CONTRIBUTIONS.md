# Codex Wheel — Hackathon contribution and provenance ledger

**Hackathon building window:** October 27–November 4, 2026.

## Pre-existing assets

A pre-event Codex Wheel Python analysis/indexing codebase exists in a separately supplied archive named `codecx-wheel-main.zip`. It includes Python, Java and JavaScript analysis utilities, repository indexing, access policy, and secret-redaction helpers. **This old codebase is not bundled in this branch.** The v3.2 architecture proposal and other technical references predate these commits; proposals are not evidence of working functionality.

## New work (2026-10-29; verification pending)

This branch introduces an AI-assisted draft of a new Java 21 synthetic refund service and Spring Boot HTTP adapter, Python refund wrapper with stable retry keys, tests, CI definition and this contribution ledger.

Actual contribution commit hashes must be recorded here **after commits are created**. The GitHub repository's initial LICENSE-only commit is not a claim of implemented functionality.

## Claim ledger

| Feature | Status | Evidence / limitation |
| --- | --- | --- |
| Public GitHub repository | verified through connected GitHub metadata | `PrasathJaga/codex-wheel` public, initial `master` only LICENSE |
| G0 source provenance | in_progress | This file; event-period commit and source pinning still required |
| Java synthetic refund service | implemented_unverified | Prior local domain smoke test; Maven CI pending |
| Python HTTP wrapper | implemented_unverified | Prior local unit tests; GitHub CI pending |
| G1 Java/Python live HTTP + protected ledger | planned | Live test must run and pass |
| G2 fault gateway | planned | Not implemented |
| G3 M1/M2 comparisons, independent oracle | planned | Not implemented |
| G4/G5 real Meta agent and investigator | planned | Not implemented |
| G6/G7 trial parity, controls, replay, evaluation | planned | Not implemented |

## Third-party dependencies and rights

Java 21, Spring Boot, Python, httpx and pytest are used under their upstream terms. The refund fixtures are synthetic. No real payment provider, production code, customer data or API credentials are included. Code generated with AI assistance requires source review and testing.

## Required provenance updates

Record exact event-period commit SHAs, experiments and model identifiers, genuine live-run results and whether any demo is recorded replay. Never imply passing tests or a successful model call without observed evidence.
