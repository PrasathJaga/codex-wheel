# Expanded amount-domain results

Tested implementation `73d476b3dadf75ab269752031199d78f424073da`; [run 41023537477](https://github.com/PrasathJaga/codex-wheel/actions/runs/41023537477). The workflow completed, while the investigator result is inconclusive. Workflow success does not mean the investigator succeeded.

| Method | Outcome | Executed plans / worlds |
| --- | --- | --- |
| C0 | Public schema unchanged; no business verdict | 0 / 0 |
| C2 budgeted fixed sampling | Regression not reproduced at sampled amounts | 18 / 108 |
| C4 range source selection | Inconclusive; proposal rejection cap reached | 0 / 0 |

All 54 baseline and 54 candidate fixed-suite worlds passed the business oracle. The investigator identified amount 5500 and the retry mechanism but submitted three rejected proposals: fault bounds excluded the chosen amount, a quote did not match its span, and citations omitted the required unchanged peer baseline. Five genuine `muse-spark-1.3` responses used 22,073 provider-reported tokens. No proposal was accepted; no manual correction, fallback plan or new run was substituted.

Ten confinement probes passed; 326 integrity checkpoints were recorded. Run wall time was 1498.395 seconds. These are measurements for this run, not general performance or monetary cost.

This author-designed case was discussed before registration and is not independently blind. Both methods had the same amount domain. C2 used fixed samples; C4 used source access but failed the acceptance requirements. The experiment provides no measured Meta superiority. Its deterministic execution differs from the earlier support-agent comparison; the results must remain separate.

[Artifact 12963453214](https://github.com/PrasathJaga/codex-wheel/actions/runs/41023537477/artifacts/12963453214), ZIP SHA-256 `51e285f92fdcc0a4d16d611063130f8f63e9041c81535dd09b066aeade6bfd8a`. Frozen comparison SHA-256 `83117febe05cd6c496709ca24be369f53b93ee34a019cb7862b8a7e3e10478af`. Machine-readable measurements: `EXPANDED_DOMAIN_RESULTS.json`. Original comparison results remain separately recorded.

Failure analysis: the final proposal cited the unchanged Python peer as `candidate`, whose bytes equal `base`, while the mediator requires an explicit `base` citation. The new range-investigator prompt did not spell out that version-label requirement. This is an interface-clarity limitation as well as an unaccepted proposal; the record does not establish that the model failed to identify the defect mechanism. The frozen run is retained without relaxing its validator or rerunning selection to obtain a win.
