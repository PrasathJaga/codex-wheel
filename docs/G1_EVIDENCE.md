# G1 live integration

Implemented: CI builds and starts Spring Boot, waits for readiness, runs the real Python wrapper over HTTP, and checks count, amount, currency, scope and effect identity through a separate token-protected evaluator read. Missing/wrong tokens must fail. Token is ephemeral and masked; it is not supplied to RefundTool.

Status: implemented_unverified until the PR Actions run succeeds. This is scripted integration, not a Meta agent/model call. The ledger is in-memory and does not survive restarts. Protection is an HTTP credential boundary, not OS isolation against hostile code. G2 durable storage, buffered fault gateway and M1/M2 experiments remain pending.
