import sys, unittest
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analysis import simulate, build_panel, analyze, cohort_did, synthetic_control


class LaunchMeasurementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runs = {}
        for name in ["growth", "migration", "broken_comparison"]:
            m, o, t = simulate(55, name)
            p, q = build_panel(m, o, t)
            cls.runs[name] = (p, q, t, analyze(p, q, t, name, bootstrap_reps=100))

    def test_sql_deduplicates_and_applies_refund_corrections(self):
        p, q, _, _ = self.runs["growth"]
        self.assertEqual(q["unique_orders"], 40 * 40 * 2 * 20)
        self.assertGreater(q["raw_rows"], q["unique_orders"])
        self.assertEqual(round(p.total_revenue.sum() * 100), q["ledger_net_cents"])
        self.assertTrue(q["reconciles"])

    def test_ledger_reconciliation_has_an_independent_reference(self):
        m, o, t = simulate(55, "growth")
        latest = {}
        for row in o:
            if row[0] not in latest or row[-2:] > latest[row[0]][-2:]:
                latest[row[0]] = row
        expected = sum(row[4] - row[5] for row in latest.values())
        self.assertEqual(self.runs["growth"][1]["ledger_net_cents"], expected)

    def test_conflicting_correction_is_rejected(self):
        m, o, t = simulate(55, "growth")
        changed = list(o[0])
        changed[4] += 100
        with self.assertRaisesRegex(ValueError, "Conflicting payloads"):
            build_panel(m, o + [tuple(changed)], t)

    def test_zero_cells_and_fixed_population_preserved(self):
        p, q, _, _ = self.runs["growth"]
        self.assertEqual(len(p), 40 * 40)
        self.assertEqual(p.eligible_at_baseline.nunique(), 1)
        self.assertTrue((p[p.week < 24].new_revenue == 0).all())
        self.assertEqual(q["missing_cells"], 0)

    def test_growth_recovers_truth(self):
        r = self.runs["growth"][3]
        self.assertLess(r["absolute_estimation_error"], 0.25)
        self.assertTrue(r["identification_checks_pass"])
        self.assertGreater(r["bootstrap_95_interval"][0], 0)

    def test_offer_success_can_be_business_loss(self):
        r = self.runs["migration"][3]
        self.assertGreater(r["new_offer_lift"], 10)
        self.assertLess(abs(r["net_revenue_lift"]), 0.25)
        self.assertLess(r["bootstrap_95_interval"][1], 0)
        self.assertIn("MIGRATION", r["verdict"])

    def test_bad_comparison_is_rejected(self):
        r = self.runs["broken_comparison"][3]
        self.assertFalse(r["identification_checks_pass"])
        self.assertIn("HOLD", r["verdict"])
        self.assertGreater(r["pretrend_slope"], 0.15)

    def test_truth_is_not_used_to_estimate(self):
        p, q, t, r = self.runs["growth"]
        changed = [(m, w, 9999, cost) for m, w, v, cost in t]
        other = analyze(p, q, changed, "growth", bootstrap_reps=100)
        self.assertEqual(r["cohort_did"], other["cohort_did"])
        self.assertEqual(
            r["synthetic_control"]["estimate"], other["synthetic_control"]["estimate"]
        )

    def test_synthetic_weights_cannot_see_post_outcomes(self):
        p, _, _, _ = self.runs["growth"]
        y = p.pivot(
            index="market_id", columns="week", values="contribution_per_eligible"
        ).to_numpy()
        c = np.array([24] * 10 + [28] * 10 + [999] * 20)
        a = synthetic_control(y, c)
        altered = y.copy()
        altered[:10, 24:] += 100
        altered[10:20, 28:] -= 100
        b = synthetic_control(altered, c)
        for aa, bb in zip(a["cohorts"], b["cohorts"]):
            np.testing.assert_allclose(aa["weights"], bb["weights"])

    def test_no_treatment_recovers_zero(self):
        rng = np.random.default_rng(12)
        y = rng.normal(0, 0.05, (40, 40)) + np.arange(40)[None, :] * 0.4
        c = np.array([24] * 10 + [28] * 10 + [999] * 20)
        self.assertLess(abs(cohort_did(y, c)[0]), 0.05)

    def test_already_treated_never_becomes_a_control(self):
        y = np.zeros((40, 40))
        c = np.array([24] * 10 + [28] * 10 + [999] * 20)
        y[:10, 24:] = 100
        _, path = cohort_did(y, c)
        later = [p["effect"] for p in path if p["cohort"] == 28]
        self.assertEqual(later, [0.0] * 8)


if __name__ == "__main__":
    unittest.main()
