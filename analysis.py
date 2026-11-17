"""Reproducible launch measurement. All observations are simulated, not Intuit data."""

from __future__ import annotations
import argparse, json, math
from pathlib import Path
import numpy as np
import pandas as pd
import duckdb
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parent
SCENARIOS = {
    "growth": {"new": 10.0, "existing": -3.0, "slope": 0.0, "label": "Added value"},
    "migration": {
        "new": 10.0,
        "existing": -10.0,
        "slope": 0.0,
        "label": "Revenue shift",
    },
    "broken_comparison": {
        "new": 10.0,
        "existing": -3.0,
        "slope": 0.65,
        "label": "Bad comparison",
    },
}
COHORTS = (24, 28)
HORIZON = 8


def simulate(seed=55, scenario="growth", noise=0.25):
    """40 markets, 40 weeks. Rollout is assigned to higher baseline markets,
    not randomized. Treatment is eligibility for an offer, never adoption.
    Known potential outcomes are written separately and never used to fit.
    Each product-market-week is split into 20 synthetic ledger charges.
    """
    cfg = SCENARIOS[scenario]
    rng = np.random.default_rng(seed)
    markets = []
    orders = []
    truth = []
    for i in range(40):
        cohort = 24 if i < 10 else (28 if i < 20 else 999)
        eligible = 1000
        # Stable level selection: early rollout markets have higher revenue.
        level = 28 + (0.35 * i if i < 20 else 0.25 * (i - 20))
        phase = (i % 5 - 2) * 0.03
        markets.append((f"M{i:02}", cohort, eligible))
        for t in range(40):
            common = 3 * math.sin(t / 6) + 0.22 * t + 2 * (t >= 24)
            trend = cfg["slope"] * t if cohort < 999 else 0
            untreated = (
                level + common + phase * math.sin(t / 3) + trend + rng.normal(0, noise)
            )
            on = t >= cohort
            # Event-time heterogeneity makes staggered rollout comparisons matter.
            ramp = 1 if not on else 1 + 0.04 * min(t - cohort, 7)
            new = cfg["new"] * ramp if on else 0
            old = untreated + (cfg["existing"] * ramp if on else 0)
            cost = 2 * ramp if on else 0
            truth.append((f"M{i:02}", t, (new + old - untreated - cost), cost))
            for product, net in [("existing", old), ("new_offer", new)]:
                cents = int(round(net * eligible * 100))
                for j in range(20):
                    net_cents = cents // 20 + (j < cents % 20)
                    # A corrected refund and an exact duplicate are deliberate traps.
                    refund = 100 if j == 0 and cents > 0 else 0
                    oid = f"{i}-{t}-{product}-{j}"
                    correct = (
                        oid,
                        f"M{i:02}",
                        t,
                        product,
                        net_cents + refund,
                        refund,
                        2,
                        2,
                    )
                    orders.append(correct)
                    if j == 0:
                        orders.append(
                            (oid, f"M{i:02}", t, product, net_cents + refund, 0, 1, 1)
                        )
                    if j == 1:
                        orders.append(correct)
    return markets, orders, truth


def build_panel(markets, orders, truth):
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE markets(market_id VARCHAR, cohort INTEGER, eligible_at_baseline INTEGER)"
    )
    market_input = pd.DataFrame(
        markets, columns=["market_id", "cohort", "eligible_at_baseline"]
    )
    con.register("market_input", market_input)
    con.execute("INSERT INTO markets SELECT * FROM market_input")
    con.execute(
        "CREATE TABLE orders_raw(order_id VARCHAR,market_id VARCHAR,order_week INTEGER,product VARCHAR,amount_cents BIGINT,refund_cents BIGINT,version INTEGER,ingested_at INTEGER)"
    )
    order_input = pd.DataFrame(
        orders,
        columns=[
            "order_id",
            "market_id",
            "order_week",
            "product",
            "amount_cents",
            "refund_cents",
            "version",
            "ingested_at",
        ],
    )
    con.register("order_input", order_input)
    con.execute("INSERT INTO orders_raw SELECT * FROM order_input")
    conflicts = con.execute("""SELECT COUNT(*) FROM (
        SELECT order_id,version,ingested_at FROM orders_raw
        GROUP BY 1,2,3 HAVING COUNT(DISTINCT (market_id,order_week,product,amount_cents,refund_cents))>1
    )""").fetchone()[0]
    if conflicts:
        con.close()
        raise ValueError(
            "Conflicting payloads share an order version; resolve upstream before reporting."
        )
    con.execute((ROOT / "panel.sql").read_text())
    panel = con.execute("SELECT * FROM market_week ORDER BY market_id,week").fetchdf()
    # Cost is a known accounting input; potential-outcome truth is not exposed here.
    cost = {(m, t): v for m, t, _, v in truth}
    panel["service_cost_per_eligible"] = [
        cost[m, t] for m, t in zip(panel.market_id, panel.week)
    ]
    panel["contribution_per_eligible"] = (
        panel.revenue_per_eligible - panel.service_cost_per_eligible
    )
    quality = {
        "raw_rows": len(orders),
        "unique_orders": con.execute("SELECT COUNT(*) FROM current_orders").fetchone()[
            0
        ],
        "panel_rows": len(panel),
        "missing_cells": int(panel.isna().any(axis=1).sum()),
        "reconciles": bool(
            np.allclose(panel.new_revenue + panel.existing_revenue, panel.total_revenue)
        ),
        "ledger_net_cents": int(
            con.execute(
                "SELECT SUM(amount_cents-refund_cents) FROM current_orders"
            ).fetchone()[0]
        ),
    }
    con.close()
    return panel, quality


def cohort_did(y, cohorts, horizon=HORIZON):
    """Simple cohort-time DiD vs never-treated; same 8-week follow-up per cohort.
    Equal baseline populations here => equal market weights. Not a full did package.
    """
    controls = np.flatnonzero(cohorts == 999)
    effects = []
    paths = []
    for g in COHORTS:
        treated = np.flatnonzero(cohorts == g)
        base = g - 1
        for e in range(horizon):
            t = g + e
            effect = (y[treated, t] - y[treated, base]).mean() - (
                y[controls, t] - y[controls, base]
            ).mean()
            effects.append(effect)
            paths.append({"cohort": g, "event_week": e, "effect": float(effect)})
    return float(np.mean(effects)), paths


def pretrend(y, cohorts):
    """Transparent warning threshold, NOT a significance test or proof of trends."""
    gaps = []
    for g in COHORTS:
        gap = y[cohorts == g, g - 12 : g].mean(0) - y[cohorts == 999, g - 12 : g].mean(
            0
        )
        gaps.append(float(np.polyfit(np.arange(12), gap, 1)[0]))
    return max(abs(s) for s in gaps)


def bootstrap(y, cohorts, reps=400, seed=919):
    """Resample whole markets, separately within rollout cohorts/control.
    Conditional on this rollout design; no correction for identification failure.
    """
    rng = np.random.default_rng(seed)
    draw = []
    groups = [np.flatnonzero(cohorts == g) for g in (*COHORTS, 999)]
    for _ in range(reps):
        idx = np.concatenate([rng.choice(g, len(g), replace=True) for g in groups])
        draw.append(cohort_did(y[idx], cohorts[idx])[0])
    return [float(x) for x in np.quantile(draw, [0.025, 0.975])]


def synthetic_control(y, cohorts):
    """Separate convex donor fit per cohort. Train weeks g-16..g-5,
    hold out g-4..g-1, then estimate the same eight post weeks as DiD.
    Fixed ridge 0.01; no outcome-based tuning or post-period fit.
    """
    results = []
    events = []
    for g in COHORTS:
        target = y[cohorts == g].mean(0)
        donors = y[cohorts == 999].T
        tr = np.arange(g - 16, g - 4)
        va = np.arange(g - 4, g)
        X = donors[tr]
        z = target[tr]
        scale = np.std(z) or 1

        def obj(w):
            return float(np.mean(((X @ w - z) / scale) ** 2) + 0.01 * np.sum(w * w))

        fit = minimize(
            obj,
            np.ones(donors.shape[1]) / donors.shape[1],
            method="SLSQP",
            bounds=[(0, 1)] * donors.shape[1],
            constraints={"type": "eq", "fun": lambda w: w.sum() - 1},
            options={"maxiter": 1000, "ftol": 1e-12},
        )
        if not fit.success:
            raise RuntimeError(f"Synthetic control failed: {fit.message}")
        gap = target - donors @ fit.x
        val_rmse = float(np.sqrt(np.mean(gap[va] ** 2)))
        results.append(
            {
                "cohort": g,
                "effect": float(gap[g : g + HORIZON].mean()),
                "validation_rmse": val_rmse,
                "weights": [float(v) for v in fit.x],
            }
        )
        for e in range(-8, HORIZON):
            events.append({"cohort": g, "event_week": e, "effect": float(gap[g + e])})
    return {
        "estimate": float(np.mean([r["effect"] for r in results])),
        "max_validation_rmse": max(r["validation_rmse"] for r in results),
        "cohorts": results,
        "event_path": events,
    }


def analyze(panel, quality, truth, scenario, seed=55, bootstrap_reps=400):
    ids = sorted(panel.market_id.unique())
    cohorts = np.array([int(panel[panel.market_id == m].cohort.iloc[0]) for m in ids])

    def matrix(col):
        return (
            panel.pivot(index="market_id", columns="week", values=col)
            .loc[ids]
            .to_numpy()
        )

    y = matrix("contribution_per_eligible")
    r = matrix("revenue_per_eligible")
    new = matrix("new_revenue") / 1000
    old = matrix("existing_revenue") / 1000
    did, events = cohort_did(y, cohorts)
    interval = bootstrap(y, cohorts, bootstrap_reps)
    sc = synthetic_control(y, cohorts)
    slope = pretrend(y, cohorts)
    # False pre-period launch: same estimator, all dates shifted eight weeks earlier.
    fake_effects = []
    for original, g in zip(COHORTS, (16, 20)):
        a = cohorts == original
        c = cohorts == 999
        fake_effects.append(
            float(
                (y[a, g : g + 8].mean(1) - y[a, g - 1]).mean()
                - (y[c, g : g + 8].mean(1) - y[c, g - 1]).mean()
            )
        )
    placebo = float(np.mean(fake_effects))
    net_lift = cohort_did(r, cohorts)[0]
    gross = cohort_did(new, cohorts)[0]
    lost = cohort_did(old, cohorts)[0]
    naive = float(
        np.mean(
            [
                y[cohorts == g, g : g + 8].mean() - y[cohorts == g, g - 8 : g].mean()
                for g in COHORTS
            ]
        )
    )
    valid = (
        quality["reconciles"]
        and slope < 0.15
        and abs(placebo) < 0.75
        and sc["max_validation_rmse"] < 1.0
    )
    verdict = (
        "HOLD: comparison fails checks"
        if not valid
        else (
            "GROWTH: contribution increased"
            if interval[0] > 0
            else (
                "MIGRATION: contribution decreased"
                if interval[1] < 0
                else "INCONCLUSIVE"
            )
        )
    )
    pre_events = []
    for g in COHORTS:
        for e in range(-8, 0):
            estimate = (y[cohorts == g, g + e] - y[cohorts == g, g - 1]).mean() - (
                y[cohorts == 999, g + e] - y[cohorts == 999, g - 1]
            ).mean()
            pre_events.append({"cohort": g, "event_week": e, "effect": float(estimate)})
    # Ground truth is used ONLY after estimation, as a simulation accuracy check.
    truth_lookup = {(m, t): v for m, t, v, _ in truth}
    actual = float(
        np.mean(
            [
                truth_lookup[m, t]
                for m, g, _ in panel[["market_id", "cohort", "eligible_at_baseline"]]
                .drop_duplicates()
                .itertuples(index=False, name=None)
                if g < 999
                for t in range(g, g + 8)
            ]
        )
    )
    return {
        "scenario": scenario,
        "label": SCENARIOS[scenario]["label"],
        "seed": seed,
        "units": "USD per baseline-eligible customer per week",
        "verdict": verdict,
        "naive_before_after": naive,
        "cohort_did": did,
        "bootstrap_95_interval": interval,
        "synthetic_control": sc,
        "new_offer_lift": gross,
        "existing_product_change": lost,
        "net_revenue_lift": net_lift,
        "contribution_lift": did,
        "pretrend_slope": slope,
        "false_launch_placebo": placebo,
        "identification_checks_pass": bool(valid),
        "simulated_truth": actual,
        "absolute_estimation_error": abs(did - actual),
        "quality": quality,
        "event_path": events,
        "pre_event_path": pre_events,
        "not_identified_by_checks": "Passing these checks does not establish parallel trends or rule out simultaneous market-specific shocks.",
    }


def run(seed=55):
    from report import render

    reports = ROOT
    results = []
    for s in SCENARIOS:
        markets, orders, truth = simulate(seed, s)
        panel, q = build_panel(markets, orders, truth)
        result = analyze(panel, q, truth, s, seed)
        results.append(result)
        panel.to_csv(reports / f"{s}-panel.csv", index=False)
    (reports / "results.json").write_text(json.dumps(results, indent=2))
    render(results, reports)
    print(
        "\n".join(
            f"{r['scenario']}: {r['verdict']} | DiD ${r['cohort_did']:.2f}, truth ${r['simulated_truth']:.2f}"
            for r in results
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=55)
    args = parser.parse_args()
    run(args.seed)
