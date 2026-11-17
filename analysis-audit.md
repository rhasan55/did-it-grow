# Checks behind the report

The code was developed with AI assistance. The following checks are executable in `test_analysis.py`; they do not depend on a model approving its own answer.

- Reconcile cents against an independent Python reduction of the latest order versions.
- Preserve all 1,600 market-week cells, including pre-launch zero revenue for the new offer.
- Reject conflicting payloads with the same order/version/ingestion key.
- Recover the known effect in the two deliberately parallel-trend simulations.
- Return a near-zero estimate when there is no effect.
- Flag the nonparallel comparison even when its estimate is positive.
- Change the simulation answer key without changing fitted estimates.
- Change post-launch outcomes without changing synthetic-control weights.
- Change the early cohort's effect without contaminating the later cohort's controls.

The SQL was also changed to load input tables in bulk rather than insert records one at a time. The input is small; no production-scale throughput claim is made.

These are checks of this implementation and these constructed cases. They cannot show that the identifying assumptions hold in real customer data.
