# Registered internal transfer pilot

Prepared after runner merge `63c0b8e27072d6955a336d185795bbb8b7964eb8`, under
unchanged v2 protocol `15a493eceaa73c71c89a64b9e1ed15fc0e0d60f597646388f32c1838f63a282e`.
No runner, prompt, adapter, oracle or protected test is changed by this pilot.

## Preparation and expected outcomes

The Codex assistant prepared both cases after the interface freeze and inspected
the existing controller tests while doing so. This is internal transfer on an
external public sample, not independent or blind evaluation. Both alter only the
allowed controller source; all upstream tests/build files remain unchanged.

Both refactor field conversion through the existing PetMapper. pc-001 copies only
editable fields onto the loaded entity. pc-002 additionally copies the mapped
owner. The public DTO marks ownerId read-only, so an omitted owner can clear that
relationship and cause a valid update to fail persistence. The expected result is
rollback/rejection, not a claim of measured ownership reassignment or data loss.

pc-001 is prospectively labeled preserving; pc-002 violating. These are authored
predictions, not measured results or independently established ground truth.
Expectation and reference-repair commitments are recorded before execution. Those
files are withheld from model inputs, not access-private files in this repository.
Model input remains the frozen source/diff/contract/action allowlist.

The source-aware conventional comparison was also AI-assisted. Four distinct
plans cover profile updates with original/alternate types, valid dates, rejected
input, missing targets and unrelated reads. Plans and citations are fixed before
outcomes; they are not an independent human baseline. No measured human effort
reduction is claimed. Upstream JUnit outcomes are retained even when they catch
the authored change.

## Launch and non-exposure

Pull-request CI validates registrations without Java execution or model requests.
The paid job runs only on the exact dedicated live branch, once, with concurrency
serialization, run-attempt gating and a prior-launch history check. It invokes
the frozen v2 CLI for each case/method sequentially. No automatic retry is allowed.
Access, baseline or execution failure stops the remaining pilot; inconclusive
investigations and abstentions remain valid recorded outcomes.

The trusted controller checks out Wheel and holds the API key. External code runs
only in the existing restricted Docker containers, which never receive that
checkout or project credentials. The parent removes the key from its environment;
only a Meta CLI child receives it, and that frozen runner removes it before any
build. Conventional children receive no key. Docker subprocess environments and
mounts remain unchanged and restricted. Raw controller logs redact the known key.
Do not add secrets or Wheel mounts to the external containers.

The launcher is orchestration/accounting added after the method freeze. It does
not change prompts, plans, model parameters, source payloads or verdicts, and never
passes conventional outcomes into Meta selection. The complete case/launcher
commit is published before the one live launch.

## Budgets and accounting

The pilot has six planned method attempts and at most six inference requests:
two simple selections and two full selection/diagnosis sequences. Abstention may
use fewer. Repairs are not part of this run. World/action/completion budgets are
the unchanged v2 limits. Every receipt, failed response and attempted world is
preserved; uncertain last-phase receipts count as attempted, not necessarily billed.

Meta's published Standard Muse Spark rates checked 1 November 2026 are $1.25/M
input, $0.15/M cached input and $4.25/M output tokens:
https://dev.meta.ai/docs/pricing-rate-limits . Standard mode is retained; the
Contributor model variant is not selected. Usage-based estimates account for
reported cache tokens; absent cache detail uses the uncached upper estimate.
Missing usage produces an unknown total, not zero. These estimates are not an
invoice, remaining credits, or historical cumulative project spending.

For planning, even counting the full published 1,048,576-token context as input
on all six requests plus the aggregate 80,000 completion-token ceiling gives
$8.20432 at these rates, before cache discounts. That is a conservative envelope
for this pilot alone, not verified account balance or prior spend.

Artifacts retain the mutable execution registry, case/method results, build logs,
world states, raw provider receipts, token usage and pricing basis. Every outcome
must remain in the final report. Do not tune a case/prompt and rerun it as the same
evaluation, manufacture an AI advantage, or call repeated worlds new discoveries.
