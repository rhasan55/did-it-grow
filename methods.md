# What is being estimated

The estimand is the average eight-week change in business contribution per baseline-eligible customer caused by making a new offer available in the treated markets. Contribution here means combined net revenue minus an illustrative service cost. It is not full profit: fixed costs, financing costs, customer lifetime value, and downstream cross-sell are outside the model.

Eligibility is fixed before launch. Treatment is availability in a market, not individual adoption. Conditioning on adoption would select on a post-treatment choice. A real deployment would also need explicit rules for identity resolution across products and for who remains in the analysis after churn.

## Simulation and scope

There are 40 fictional markets and 40 observation weeks. Ten markets launch in week 24, ten in week 28, and twenty never launch. Market selection depends on baseline revenue, so treatment is not randomized. Every market has 1,000 baseline-eligible customers. The ledger contains 64,000 unique synthetic charge records, plus duplicate deliveries and earlier versions that omit a later refund. These records are an accounting simulation, not a behavioral model of individual tax filers.

The three scenarios share the same seed, market structure, calendar effects, and noise. They are deliberately constructed examples, not a benchmark of how often either estimator succeeds in real data. Geography and staggered timing are hypothetical; Intuit has not said that its program uses this rollout design.

## SQL contract

`panel.sql` takes the latest version of each order, recognizes refunds against its original order week, aggregates across both products, and joins a complete market-week spine. The fixed baseline denominator retains customers who never purchase. Money is stored in cents until aggregation. A second run rebuilds rather than appends the output.

The demonstration has a unique latest correction for each order; equal-key deliveries are identical. Production ingestion would need to reject conflicting payloads with the same order/version/ingestion key. Do not silently resolve conflicting corrections using row order.

A production warehouse would partition scans by order week, track changed order IDs, MERGE their current state, and rebuild every affected historical partition when refunds arrive. This local example demonstrates those semantics with a full rebuild. It is not an implemented warehouse orchestration system or a scale benchmark. The generated CSVs include already-aggregated zero-filled reporting panels for inspection.

## Cohort DiD

For each rollout cohort g and event week e = 0..7, subtract its change from week g-1 to week g+e from the corresponding never-treated change, with the sign arranged as treated minus control. Average the resulting cohort-time effects. Equal cohort sizes and baseline populations make equal weights appropriate in this example. The later cohort is never compared against the already-treated earlier cohort.

This is a simple cohort-time estimator inspired by the modern staggered-adoption literature, not an implementation of the full Callaway–Sant'Anna estimator, doubly robust adjustment, or its inference procedure. No covariate reweighting is needed in the two deliberately parallel-trend worlds. The broken-comparison world violates that assumption on purpose.

The percentile interval resamples whole markets within their original cohort/control strata, 400 times with a fixed seed. It preserves within-market serial dependence, but is conditional on this rollout design. There are only ten treated markets per cohort. The interval does not account for unobserved confounding, interference, model-selection uncertainty, or common shocks correlated across markets. It is not a promise of nominal coverage.

## Synthetic control

Fit each cohort's mean outcome as a convex combination of the twenty never-treated market series. Nonnegative weights sum to one. Fit the twelve weeks g-16..g-5, hold out the four weeks g-4..g-1, then evaluate the same eight post-launch weeks as DiD. The fixed ridge penalty is 0.01 after scaling the training loss. No post-launch data selects weights or tuning parameters. The report shows held-out RMSE, not only training fit.

No confidence interval is reported for synthetic control. This is a robustness comparison, not an independent replication: both methods share the same donors and can fail together. The high-baseline later cohort can be near or outside donor support; held-out error makes that limitation visible. There is no in-space placebo p-value, and none should be inferred.

## Checks and decision language

The example flags a pre-launch gap slope above $0.15 per customer per week, a false-launch effect above $0.75 in absolute value, or synthetic-control validation RMSE above $1. These are visible illustrative tolerances, not statistical significance tests. The false launch is eight weeks early and its full evaluation window ends before the real launch. A flagged scenario is marked HOLD, even if an interval excludes zero.

A passing scenario may be labeled growth or migration *in this simulation*, based on its contribution interval. Passing checks does not establish parallel trends. A market-specific change appearing exactly at launch could be invisible to every pre-period diagnostic. Before using this on actual data, investigate concurrent marketing/pricing changes, spillovers, anticipation, donor exposure, missing accounts, differential trends, and delayed revenue recognition.

The sensitivity slider subtracts an assumed extra treated-market trend times 4.5 weeks, the average distance from the baseline week to the eight outcome weeks. It shifts the point estimate and interval equally. This is an interpretable bias calculation, not an HonestDiD bound or a replacement for research design.

## Why the ledger matters

A causal estimator cannot rescue an outcome with duplicated orders, ignored refunds, cross-product revenue omitted, or a denominator changed after launch. The SQL tests and accounting reconciliation come before interpreting the estimate.

## References

- Callaway and Sant'Anna, [Introduction to DiD with Multiple Time Periods](https://bcallaway11.github.io/did/articles/multi-period-did.html).
- Abadie (2021), [Using Synthetic Controls: Feasibility, Data Requirements, and Methodological Aspects](https://www.aeaweb.org/articles?id=10.1257/jel.20191450).
