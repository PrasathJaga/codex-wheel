# G4: bounded real Meta support-agent slice

Status at implementation: runtime verification pending. Existing G2/G3 evidence uses zero model calls; this change does not relabel those results.

The trusted gateway uses the OpenAI Python SDK with `https://api.meta.ai/v1`, `MODEL_API_KEY`, and `muse-spark-1.3`, matching the integration blueprint and current Meta documentation:
- https://dev.meta.ai/docs/quickstart
- https://dev.meta.ai/docs/protocols/chat-completions
- https://dev.meta.ai/docs/tool-calling

Two genuine initial model requests select refund tool arguments for synthetic M1/M2 customer messages. Exact schema and independent authorization checks precede freezing the full assistant message, tool-call identity, conversation and canonical arguments. This is schema/authorization preflight, not a separate model-based or mocked-tool preflight. Each frozen intent is replayed in baseline and candidate. The actual wrapper generates its own idempotency key in each world, preserving the M2 fault mechanism. Each actual receipt is returned to Meta for a genuine final customer-facing response. That response is evidence only; the independent protected ledger oracle decides correctness.

The bounded slice has one paired trial per mutation with its fault active (four worlds), at most six generation attempts, no SDK retries, and at most 1,024 completion tokens per attempt. It is not a statistical benchmark, G5 investigator, or replacement for the 48-world manual control matrix. Chat Completions replays messages but does not preserve hidden reasoning across turns. Model availability and credit entitlement are established only by actual successful requests; the nominal credit balance is not verified here.

`MODEL_API_KEY` is consumed by the trusted parent and removed from its environment before builds or Java/wrapper subprocesses. Child environments allow only runtime plumbing; the evaluator token goes only to Java and the trusted evaluator, not the wrapper. This is process separation on a trusted runner, not a hostile-code OS sandbox. Neither request headers nor exception response bodies are artifacts. Synthetic prompts, assistant messages, receipt replies, IDs, usage, frozen hashes, ledger rows, proxy events and source variants are retained.

The dedicated workflow runs only on manual dispatch or code changes to the named G4 implementation branch; PRs and ordinary master pushes do not spend credits. Every dispatch/re-run can consume another bounded budget. GitHub stores the key as repository Actions secret `MODEL_API_KEY`; never paste it into code or conversation. No Baseten deployment is needed for this slice.

Success requires successful model turns AND baseline ledger pass / candidate duplicate-effect failure for both mutations, plus existing commit-before-fault and persisted-ledger restart checks. A failed model request or malformed intent fails closed; no successful G4 summary is emitted.

## Observed execution — 2026-10-29

The bounded slice is **experimentally verified** at commit `c295b9d27072ee207cb5cf61cb52ad01efd24526`, Actions [40868779979](https://github.com/PrasathJaga/codex-wheel/actions/runs/40868779979). This supersedes the implementation-time pending status above, not the explicitly incomplete full G4 gate.

Inspected artifact [12894409373](https://github.com/PrasathJaga/codex-wheel/actions/runs/40868779979/artifacts/12894409373):
- ZIP SHA-256: `0991af39636f9cfdb306ce05d44027149bc925527e6cf105bf78966d4e3afa68`
- Frozen plan SHA-256: `0d5d871df14b73670eac1fe63602d0ba011d7fdca49251cd217debac20a460ec`
- Six successful genuine `muse-spark-1.3` calls: two tool selections, four post-tool text responses. Provider-reported total tokens: 5,376; this is not a dollar-cost measurement.
- M1/drop: baseline one effect, candidate two; independent oracle true/false.
- M2/502: baseline one effect, candidate two; independent oracle true/false.
- All four worlds recovered the same ledger on restart. Actual drop paths recorded `RemoteProtocolError`.
- The model reported successful refunds in both faulty worlds despite duplicate effects. This establishes the disclosed synthetic cases only, not general model reliability or superiority.

The first run [40868461679](https://github.com/PrasathJaga/codex-wheel/actions/runs/40868461679) produced two successful initial tool calls, then failed on a continuation HTTP 400. The implementation had supplied unsupported `tool_choice="none"`. Meta documentation permits only `auto`; the corrected run uses it and still rejects further tool execution. Across these two runs there were eight successful generations and one rejected request. Failed-run usage was 1,685 tokens for its successful generations. No credit balance or billed total was queried.

Next: implement and verify the full mocked-tool preflight, then the G5 investigator and remaining controls/isolation/evaluation gates. This evidence must not be labeled full architecture completion.
