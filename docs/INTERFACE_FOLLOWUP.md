# Proposal review and interface follow-up v2

The first expanded-domain run (41023537477) is preserved as inconclusive. A fail-fast validator hid simultaneous defects:

| Submission | Invalid fields | Attribution |
| --- | --- | --- |
| 1 | Amount 5500 with fault bounds 1–1; Java quote has two lines but declares seven; unchanged peer cited as candidate | Parameter and citation mistakes; amount-bound units and mandatory base label were not explicit in the prompt/schema |
| 2 | Corrected fault bounds; same incorrect Java span and peer label | Citation mistake persists; peer-version interface requirement remains undisclosed |
| 3 | Correct one-line quotes and bounds; peer still cited as candidate | Interface contract mismatch: peer candidate bytes equal base, but the validator requires explicit base and the feedback did not name that requirement |

All proposals identified amount 5500 and the duplicate-retry mechanism. This shows a plausible hypothesis, not an accepted or runtime-verified experiment. It does not prove whether model mistakes or interface clarity would dominate another attempt.

Decision: one small diagnostic follow-up is justified. `evaluation/interface_followup_v2.json` freezes two fresh arms in order: original developer prompt and clarified developer prompt. The added text states the existing rules for amount-bound units, exact inclusive source spans, actual source reads, required changed-candidate and unchanged-peer-base references, and submission limits. It supplies no target amount, defect explanation, prior proposals or outcomes. The source case, tool schemas, validator, provider configuration, deterministic arguments and runtime oracle stay identical. No validator relaxation or manual repair is allowed.

Fixed limits: one invocation per arm; six model calls and at most three rejected proposals per arm; twelve investigator calls total; 2048 completion-token ceiling per call (24576 total output capacity); 100000 message characters per call; zero support calls; no SDK retries. Both selections freeze before worlds. Each accepted arm gets one selected plan and one no-fault control, three fresh pairs per plan: at most 24 worlds total. Rejection, abstention and errors remain results. The verified historical 108-world fixed suite is referenced, not rerun or relabeled as fresh.

Interpretation: one known case and one selection per arm can test whether the clarified interface can produce an accepted, executable experiment. It cannot establish a statistically isolated prompt effect, blind discovery, population success rate or general Meta superiority. Sampling variance and fixed arm order are explicit limits. Both new outcomes and the original failure must be published, even if the control wins or both fail. No additional run is scheduled to seek a desired winner.
