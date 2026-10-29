# G2 / G3 manual counterfactual protocol

G1 verified at commit 4b912e0574013d743d6c5921288e143f44085e9d, Actions run 40856908942: live integration test passed (1 passed, no skip).

This branch implements a bounded loopback buffering gateway, single-process forced append ledger, and manual M1/M2/B1/B2 matrix. Status: implemented_unverified pending Actions. Plans and source/oracle hashes are recorded before building/running worlds. Each case includes no-fault and fault protocols, three trials, fresh Java process/ledger/gateway per world, protected ledger reads and process restart recovery. Seeded mutation sources are saved with evidence. A failure stops the matrix and prevents a verified summary.

M1 modifies Java low-value deduplication, Python fixed. M2 modifies only Python 502 key handling, Java fixed. B1/B2 make actual benign source edits. Counts, totals, scope, currency, key hashes and actual transport exception types are captured. The gateway cannot reach evaluator routes and receives no evaluator token.

Limits: synthetic, known defects; zero Meta calls; no AI discovery, assistant continuation, model benchmarks or comparative superiority. Sequential single-process append log is not a production transaction database. Graceful restart verification is not a power-loss guarantee. Malformed log fails startup; multi-process writers unsupported. Same-host trusted test orchestration is not a hostile-code sandbox or OS-protected oracle. Full DSL/preflight, durable database, independently mounted authorization registry, artifact signatures, general replay and genuine Meta roles remain future gates. Existing full_order-only API does not yet support the architecture's legitimate partial-refund counterexample.

Run automatically in Actions; no laptop required. Download manual-counterfactual-evidence from the run for frozen plans, raw per-world rows, source variants and logs.
