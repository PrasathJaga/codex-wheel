# Bounded M1 repair verification

This separate experiment asks Meta for one condition edit after showing the recorded M1 source change and three failing candidate worlds from comparison run 41009784244. The original ZIP and frozen plan hashes are verified before inference. One request, one proposal attempt, 2048 completion-token limit, no retries. Exact policy: `evaluation/repair_v1.json`.

The trusted runner applies a structured text replacement only to the reviewed deduplication condition. It admits the output only when the complete file equals the reviewed healthy baseline bytes. This is a bounded baseline-restoration demonstration, not general autonomous patch synthesis. The model cannot change paths, oracle, fixture, tests or gateway. A rejected proposal ends the run; no manual fallback is substituted.

The runner executes Java tests on the admitted repair, then re-executes all eight original M1 plans twice: healthy baseline versus broken candidate, and healthy baseline versus repaired candidate. Each plan has three fresh pairs: 96 worlds maximum, zero support-agent calls. Plans retain original arguments, authorizations and fault rules. The broken selected plan must reproduce; every repaired plan must pass. New source hashes identify the intentional repaired candidate. No new discovery or population repair-success claim is made.

Only the named live branch/manual workflow invokes inference. Evidence includes the raw request/proposal, generated unified diff, repaired source, test log, both stages' worlds/ledgers, protected checks and outcomes. The application branch is not patched or merged automatically. Complete runtime binary closure is not exported.
