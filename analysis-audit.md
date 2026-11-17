# Four ways a convincing launch analysis can be wrong

This project was developed with AI coding assistance. Its claims are checked by executable tests, accounting reconciliation, pre-period diagnostics, and simulation truth. There is no AI model in the analysis runtime.

The examples below are deliberately written failure cases. They are not presented as outputs obtained from a named model, or as incidents from an employer.

| Tempting claim or implementation | Why it fails | What this project does |
| --- | --- | --- |
| “The new offer earns more revenue, so the program grew the business.” | Customers may have moved from an existing product. Service costs can make the combined contribution negative. | Reconcile both products and costs before estimating impact. |
| Join every delivered order event and SUM revenue. | Retries duplicate deliveries; earlier versions omit refunds. | Resolve the current order version first, then aggregate. A cent-level reconciliation checks the result. |
| Fit one two-way fixed-effects regression to all staggered adopters. | Already-treated markets can become controls under heterogeneous effects. | Use explicit cohort-time comparisons against never-treated markets. A test changes the earlier cohort's effect and checks that the later cohort does not inherit it. |
| “The interval excludes zero, so the launch worked.” | A confidence interval describes sampling variation under assumptions; it cannot cure a broken comparison. | A deliberately nonparallel world gets HOLD despite an attractive estimate. |

Two further tests target subtle mistakes: changing simulation truth must not change the estimate; changing post-launch outcomes must not change synthetic-control donor weights.

The useful skill is being able to explain why an output is wrong, produce a failing check, and fix the measurement—not calling an analysis trustworthy because an AI generated it or two methods agree.
