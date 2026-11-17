# Did it grow?

**A new offer can win customers from your own product. The launch dashboard still looks great.**

![A launch win and a business loss, using simulated data](preview.svg)

I built a small launch-measurement example around one question: **did the business grow, or did customers just move?**

In one simulated rollout, the new offer adds **$11.40** in revenue per baseline-eligible customer per week. Existing-product revenue falls **$11.39**. After service costs, combined contribution falls **$2.27**. Looking only at the new offer would call this a win.

[Open the interactive report](https://rhasan55.github.io/did-it-grow/) · [Read the analysis](analysis.py) · [Inspect the SQL](panel.sql)

All data is simulated. This is an independent example inspired by public consumer-finance launches, not an estimate of Intuit performance or a claim about a real program. No model API runs in this project.

## Try it in two minutes

Download the repository, open `index.html` in a browser, and switch between three worlds:

| World | Cohort DiD contribution | Decision in the example |
| --- | ---: | --- |
| Real growth | +$5.71 | Positive contribution under the simulated assumptions |
| Customers switch products | −$2.27 | New-offer revenue hides a business loss |
| Broken comparison | +$8.63 | HOLD: pre-launch diagnostics fail |

The slider asks how large an unmeasured differential trend would need to be to change your conclusion. It is a simple bias calculation, not a formal identification guarantee.

## Reproduce

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python analysis.py
python -m unittest -v test_analysis.py
```

Tested with Python 3.12, NumPy 2.3.5, pandas 2.2.3, DuckDB 2.0.0, and SciPy 1.18.1. Exact tested versions are pinned in `requirements.txt`. The default seed is 55; `python analysis.py --seed 123` regenerates the example. Exact displayed values refer to seed 55.

## What is inside

- **SQL reporting:** resolve duplicate deliveries and refund corrections; preserve the full eligible population; reconcile both products to the ledger.
- **Cohort-time DiD:** compare each rollout cohort with never-treated markets, with the same eight-week follow-up window.
- **Synthetic control:** fit nonnegative donor weights before launch and check a held-out pre-launch window.
- **A refusal case:** a positive estimate does not override failed comparison checks.
- **Nine tests:** money reconciliation, zero cells, simulation recovery, negative controls, information leakage, and staggered treatment contamination.

The local dataset has 40 markets, 40 weeks, and 64,000 unique synthetic ledger records. This demonstrates SQL semantics, not warehouse-scale performance. Potential-outcome truth checks estimator recovery but never enters estimation.

## The judgment behind the result

A passing pre-trend check does not establish parallel trends. A national launch may have no unaffected controls. Concurrent price changes, spillovers, or a shock appearing exactly at launch could invalidate both estimates. The report makes that stopping point visible.

[Methods and limitations](methods.md) · [Analysis-error audit and AI disclosure](analysis-audit.md) · [Public context and sources](sources.md)

Built by Raja Hasan. MIT license.
