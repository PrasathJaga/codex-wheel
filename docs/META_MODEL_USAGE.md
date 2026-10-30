# Verified Meta model usage

Codex Wheel uses the Meta Model API in two functional roles: a source-reading investigator chooses constrained experiments, and a support agent selects a refund tool and responds to its actual result. Deterministic verification/replay is a separate phase.

## Provider and executable code

- Model requested: `muse-spark-1.3`.
- API base URL: `https://api.meta.ai/v1`.
- The `OpenAI` Python class is an OpenAI-compatible client configured with that Meta endpoint and model ID. It does not select the provider by its class name.
- [Trusted gateway/client](https://github.com/PrasathJaga/codex-wheel/blob/d9801353f28df4a35d8d56e4ed9757628e6f45b1/wheel/meta_agent.py).
- [Investigator source tools and real model loop](https://github.com/PrasathJaga/codex-wheel/blob/d9801353f28df4a35d8d56e4ed9757628e6f45b1/wheel/investigator.py).
- [Genuine G6 workflow](https://github.com/PrasathJaga/codex-wheel/blob/367626239f7acc703e9e0c693117a0c8718377e9/.github/workflows/g6-repeatability.yml).

The parent gateway owns `MODEL_API_KEY`. Execution containers do not receive it. Offline tests using fake clients are not counted as genuine inference.

## Inspected genuine run

Actions [40881599825](https://github.com/PrasathJaga/codex-wheel/actions/runs/40881599825), code `367626239f7acc703e9e0c693117a0c8718377e9`, passed. Its inspected artifact is [12901497160](https://github.com/PrasathJaga/codex-wheel/actions/runs/40881599825/artifacts/12901497160).

| Role | Genuine responses in this run | Functional contribution |
| --- | --- | --- |
| Meta investigator | 18 | Read diff/source through mediated tools, proposed source-cited customer/amount/fault experiments, corrected rejected proposals and abstained on benign changes |
| Meta support agent | 52 | Four initial real tool selections/mock preflights, followed by 48 real post-tool continuations after actual backend worlds |
| Total for this G6 run | 70 | Both model roles executed through Meta's API |

Reinspection confirmed that every one of those 70 archived responses identifies `muse-spark-1.3` and includes a provider response ID and usage object. Investigator tool history includes four diff reads, fourteen source reads, six proposal invocations (including revisions/rejections), and two abstentions. These counts are not accepted-plan counts or discovered-bug counts. The run's 48 worlds established the bounded effects described in G6_REPEATABILITY.md.

This is one verified successful run. Earlier G4/G5 and failed-run usage are recorded separately; 70 is not claimed as the project's lifetime request total. No billed dollar cost or remaining credit balance is inferred.

## Why replay has zero new Meta calls

The live analysis path records and freezes a Meta-selected experiment before differential execution. Replay then consumes that fixed plan and tool intent so another runner can check the same intervention and business effect. Choosing another plan during replay would change the experiment being reproduced.

The default replay workflow therefore uses no new inference and labels its mode `deterministic_tool_backend_replay`. Original model messages are preserved as recorded evidence; fresh messages are not fabricated. Optional fresh post-tool continuations require an explicit flag, SDK and key; the zero-key replay workflow does not exercise that option.

The current project contains both the genuine Meta-driven analysis path and the deterministic replay path. Building or running the latter does not remove the former.

## Stage One and demo presentation

For the user's quoted Stage One criterion, the substantive evidence is that Meta selects source-grounded experiments and participates in the actual agent/tool workflow during the hackathon. The project theme recorded in project sources is Push the Frontier; its demonstrated direction is verification of agent/tool/backend behavioral drift with source-grounded experiment synthesis and an independent ledger oracle.

This supports a factual explanation of theme fit and meaningful Meta use. Organizer eligibility/viability judgments remain the judges' decision. No finalist ranking or competition certification is claimed.

The demo/submission should show:

1. The real Meta investigation/tool trace before outcomes, including source references and the selected drop/502 intervention.
2. The genuine support-agent tool selection and actual post-tool messages.
3. The separately protected business assertions and observed ledger effects.
4. Replay clearly labeled as replay, with its zero-new-inference mode visible.

The scope remains disclosed synthetic seeded refund cases; no generic discovery advantage over fixed tests has yet been measured. Preserve abstentions, inherited benign controls and failed attempts. Never expose the key or present an offline fake-client test as a provider request.
