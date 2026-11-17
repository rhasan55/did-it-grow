# Design and limits

## Outcome

The target is the average eight-week effect of making an offer available on contribution per baseline-eligible customer in rollout markets. Contribution combines revenue from both products, net of refunds, less an illustrative service cost. It excludes fixed costs, financing costs, lifetime value, and later cross-sell.

Treatment is offer availability, not adoption. The eligible population is fixed before launch. Restricting the analysis to adopters would select on a post-treatment choice.

## Data

Forty fictional markets are observed for forty weeks. Ten launch in week 24, ten in week 28, and twenty never launch. Market selection depends on baseline revenue; it is not randomized. Each market has 1,000 baseline-eligible customers.

The 64,000 unique ledger records split each market/product/week total into twenty entries, including zero entries. Duplicate deliveries and earlier versions that omit a refund are added on purpose. These are accounting records from a simulation, not a behavioral model of individual filers.

`panel.sql` selects the latest order version, attributes refunds to the original order week, and joins a complete market-week spine. Conflicting payloads at the same version key are rejected. Money stays in cents until aggregation. An independent Python reduction checks the ledger total.

The example rebuilds locally. In a warehouse, corrections would need a keyed MERGE and recomputation of affected historical partitions. Neither that orchestration nor a scale benchmark is implemented here.

## Difference in differences

For cohort g and post-launch week t, estimate:

    ATT(g,t) = mean(Y_t - Y_(g-1) | cohort g)
               - mean(Y_t - Y_(g-1) | never treated)

Average over the first eight post-launch weeks and both equal-sized cohorts. The later cohort is never compared with an already-treated cohort. Pre-launch points use the same baseline week for a diagnostic plot; they do not enter the effect average.

This is a simple cohort-time estimator, not the full Callaway–Sant'Anna implementation. It relies on parallel untreated trends, no anticipation, and no spillovers. Stable baseline level differences are allowed; different underlying trends are not.

The interval uses 400 whole-market bootstrap draws, resampled separately within each cohort/control stratum. That preserves within-market serial dependence, conditional on the rollout. With only ten treated markets per cohort, it is not a guarantee of nominal coverage. It does not cover confounding or shocks correlated across markets.

## Synthetic control

For each cohort, fit a convex combination of never-treated market series: nonnegative weights summing to one. Train on g-16 through g-5; hold out g-4 through g-1; evaluate the same eight post-launch weeks. The ridge penalty is fixed at 0.01 after scaling the training loss. Post-launch outcomes never select weights or tuning parameters.

The report shows the worst cohort's held-out RMSE. No synthetic-control confidence interval or placebo p-value is claimed. Both estimators use the same donors and can fail together. The higher-baseline cohort can be near or outside donor support, which is visible in held-out error.

## When to stop

Demo review tolerances are $0.15 per customer per week for the pre-launch gap slope, $0.75 for the absolute false-launch effect, and $1 for held-out RMSE. These are explicit illustrative tolerances, not significance tests. The false launch is eight weeks early; its evaluation ends before the actual launch.

Passing those checks does not establish parallel trends. A new market-specific shock at rollout could evade every pre-period diagnostic. National launches may have no unaffected donor markets. Check contemporaneous pricing, marketing, eligibility, identity resolution, and spillovers before using this design.

The slider subtracts an assumed differential trend multiplied by 4.5 weeks, the mean distance from the baseline week to the outcome weeks. It shifts the estimate and interval equally. This is a bias calculation, not a formal sensitivity bound.

## References

- Callaway and Sant'Anna, [DiD with Multiple Time Periods](https://bcallaway11.github.io/did/articles/multi-period-did.html).
- Abadie (2021), [Using Synthetic Controls](https://www.aeaweb.org/articles?id=10.1257/jel.20191450).
