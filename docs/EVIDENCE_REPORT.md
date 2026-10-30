# Evidence report renderer

`python -m wheel.report_visualizer` creates a self-contained HTML view of recorded comparison evidence. It checks the supplied frozen-plan hash, pair identities, actual effects against the oracle, post-commit event evidence and TSV/record agreement before rendering. Model/source strings are escaped. It invokes no model and performs no runtime replay.

Required arguments: `--comparison DIRECTORY --comparison-hash TRUSTED_PLAN_SHA256 --output REPORT.html`. Optional expanded evidence: `--expanded DIRECTORY --expanded-hash TRUSTED_PLAN_SHA256`. Optional bounded repair: `--repair DIRECTORY --repair-hash TRUSTED_REPAIR_LOCK_SHA256`.

Use original artifact ZIP hashes to establish archive identity before extraction; the plan hash alone does not authenticate model replies or every evidence file. Obtain trusted roots independently of downloaded sidecars. Repair stage plans are checked against the parent repair lock. Recorded text remains labeled recorded, deterministic worlds have no fabricated model response, and failed/inconclusive selections remain visible.
