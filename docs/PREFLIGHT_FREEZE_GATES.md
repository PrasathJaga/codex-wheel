# Mocked-tool preflight and mandatory integrity gates

Implementation status: implemented, runtime CI/live verification pending for this change. Earlier G4 six-call evidence remains attributable to PR #5, not to these new gates.

Source requirements: v3.2 master architecture sections 7 (steps 6–8), 13 and 22; updated START_HERE. The architecture's G4 row concerns genuine support-agent tool selection/continuation, already demonstrated in PR #5. Mocked-tool preflight and freeze are also prerequisites for G5 investigation. Earlier project notes calling this a remaining “full G4” task were shorthand; this update does not redefine or claim completion of all architecture gates.

## Implemented behavior

1. The real Meta support agent selects a tool from the synthetic customer dialogue. Strict schema/authorization validation precedes dispatch to `MockRefundTool.issue_refund`. That mock has no HTTP client, backend reference, ledger or credentials; it records the arguments and returns explicitly `mock_only` / `validated_without_execution`.
2. Both preflights must succeed before any accepted seed is exposed or any Java build/world begins. A failure records `trigger_not_reached`, freezes no plan and starts no worlds. This implementation uses one attempt per trigger and fails closed; an investigator repair loop remains future work.
3. The full original assistant message/tool-call ID and canonical arguments are frozen. The mock receipt is recorded separately and never appended to the real-world conversation. Wrapper-generated retry keys remain unfrozen.
4. The runner persists `preflight.json`, `tool_intent_seed.json`, `locked_experiment.json`, its SHA-256 sidecar, and the compatible `frozen-plan.json` before builds/worlds. Source, policy, oracle, proxy, wrapper, authorization/intent and plan hashes are bound. Generated JAR hashes are bound after building and before execution.
5. Mandatory checks run before builds, each world start/restart, each wrapper invocation, each continuation and final summary. Replacing a plan and its checksum file does not reset trusted expected hashes. Changed/missing/symlinked bound files fail closed. Raw trial JSON is checked against the trusted in-memory record before summary publication. Reusing a nonempty evidence directory is rejected to prevent an old success summary being mistaken for a new run.

## Verification protocol and limits

Offline tests use explicitly fake model responses and fake build outputs only for negative-path enforcement. They must never count as live Meta calls or genuine Java executions. Live validation uses the dedicated workflow on `hackathon/preflight-freeze-gates`: at most six real generations, no SDK retries, two preflights and four post-tool responses, with actual Java/Python fault trials and protected ledger assertions. Ordinary PR/master pushes do not run paid inference. Existing 48-world manual regression tests remain separate.

The mock validates reachability and arguments, not refund success. It does not require an additional model continuation; both actual world receipts receive real post-tool turns. Neither model wording nor mock success can override the ledger oracle.

Limitations: same-host trusted-runner checks, not hostile-code isolation, signed attestations or prevention of every check/use race. Model gateway and runner share a trusted process. Dependencies are version ranges with runtime versions recorded, not fully locked reproducible builds. The investigator, its source-tool allowlist/repair loop, three-trial live-model matrix, legitimate partial-refund controls, fair C0/C2/C4 evaluation and portable replay command remain incomplete. No generalization, superiority or full-project completion claim follows from this step.
