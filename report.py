"""Render an offline review of the estimates in results.json."""

import html
import json


def money(value):
    return f'{"+" if value >= 0 else "−"}${abs(value):.2f}'


def chart_svg(result):
    """Keep the same axis across cases so a bad pre-period fit stays visible."""
    did = result["pre_event_path"] + result["event_path"]
    synthetic = result["synthetic_control"]["event_path"]
    paths = []
    for observations, color in [(did, "#a3482c"), (synthetic, "#27677a")]:
        means = {
            week: sum(
                row["effect"] for row in observations if row["event_week"] == week
            )
            / 2
            for week in range(-8, 8)
        }
        paths.append((means, color))
    left, right, top, bottom = 56, 748, 18, 218
    x = lambda week: left + (week + 8) * (right - left) / 15
    y = lambda effect: bottom - (effect + 5) * (bottom - top) / 40
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 780 260" role="img" '
        'aria-label="Estimated contribution change before and after rollout. '
        'Orange is cohort DiD; blue is synthetic control. The same scale is used in all three cases.">',
        '<rect width="780" height="260" fill="white"/>',
    ]
    for tick in [-5, 0, 10, 20, 30, 35]:
        svg.append(
            f'<path d="M{left},{y(tick)}H{right}" stroke="#e1e3e2"/>'
            f'<text x="45" y="{y(tick)+4}" text-anchor="end" '
            f'font-family="sans-serif" font-size="11">{tick}</text>'
        )
    svg.append(
        f'<path d="M{x(-.5)},{top}V{bottom}" stroke="#777" stroke-dasharray="3 4"/>'
    )
    for week in [-8, -4, 0, 4, 7]:
        svg.append(
            f'<text x="{x(week)}" y="239" text-anchor="middle" '
            f'font-family="sans-serif" font-size="11">{week}</text>'
        )
    for points, color in paths:
        xy = " ".join(
            f"{x(week):.2f},{y(effect):.2f}" for week, effect in points.items()
        )
        svg.append(
            f'<polyline points="{xy}" fill="none" stroke="{color}" stroke-width="2"/>'
        )
        for week, effect in points.items():
            svg.append(
                f'<circle cx="{x(week)}" cy="{y(effect)}" r="2.5" fill="{color}"/>'
            )
    svg.append("</svg>")
    return "".join(svg)


def case_section(result):
    r = result
    cost = r["net_revenue_lift"] - r["contribution_lift"]
    if r["scenario"] == "migration":
        conclusion = "The offer grew. Combined contribution fell."
        interpretation = (
            "The new offer gained about as much revenue as the existing product lost. "
            "Service costs turned that near-zero revenue change into a contribution loss. "
            "I would not expand the offer on these eight-week economics alone."
        )
    elif r["scenario"] == "growth":
        conclusion = "The gain survives the cross-product accounting."
        interpretation = (
            "The existing product lost some revenue, but the new offer more than covered "
            "that loss and the added service cost. I would still investigate concurrent "
            "changes and longer-term outcomes before treating this as a rollout decision."
        )
    else:
        conclusion = "The estimate is positive. The comparison is not usable."
        interpretation = (
            "Rollout markets were already growing faster before launch. Synthetic control "
            "also misses the held-out pre-period badly. A narrow interval around the DiD "
            "estimate does not fix either problem. I would seek a different comparison."
        )
    rows = [
        ("New offer", r["new_offer_lift"]),
        ("Existing product", r["existing_product_change"]),
        ("Added service cost", -cost),
        ("Combined contribution", r["contribution_lift"]),
    ]
    accounting = "".join(
        f"<tr><td>{name}</td><td>{money(value)}</td></tr>" for name, value in rows
    )
    low, high = r["bootstrap_95_interval"]
    return f"""
<section id="{r['scenario']}" class="case" hidden>
  <h2>{conclusion}</h2>
  <p>{interpretation}</p>
  <div class="two-columns">
    <div>
      <h3>Where the change comes from</h3>
      <p class="unit">Estimated change, USD per eligible customer per week</p>
      <table class="accounting"><tbody>{accounting}</tbody></table>
      <p class="small">DiD estimate: {money(r['cohort_did'])}. 95% market-bootstrap interval:
      {money(low)} to {money(high)}. Costs are illustrative; this is not full profit.</p>
    </div>
    <div>
      <h3>Does the comparison hold up?</h3>
      <table class="checks"><tbody>
        <tr><td>Pre-launch gap trend</td><td>${r['pretrend_slope']:.3f}/week</td></tr>
        <tr><td>False launch, 8 weeks early</td><td>{money(r['false_launch_placebo'])}</td></tr>
        <tr><td>Synthetic control, held-out RMSE</td><td>${r['synthetic_control']['max_validation_rmse']:.2f}</td></tr>
      </tbody></table>
      <p class="small">Review thresholds: $0.15/week, $0.75 absolute effect, and $1 RMSE.
      These are fixed demo tolerances, not significance tests.</p>
      <p class="status">{'Checks pass in this simulation' if r['identification_checks_pass'] else 'Checks fail. Do not interpret the estimate causally.'}</p>
    </div>
  </div>
  <h3>The pre-period matters</h3>
  <p class="small">USD per eligible customer per week, relative to the estimated counterfactual.
  Weeks are relative to launch; the dashed line marks rollout.</p>
  {chart_svg(r)}
  <p class="legend"><span>Cohort DiD</span><span>Synthetic control</span></p>
  <p class="small">Both methods share the same never-treated markets. Agreement would not
  rule out a shock affecting only rollout markets at launch. The synthetic-control estimate
  is {money(r['synthetic_control']['estimate'])}; no uncertainty interval is claimed for it.</p>
  <details><summary>Check the answer against the simulation</summary>
    <p>The generator's known contribution effect is {money(r['simulated_truth'])}.
    The DiD estimation error is ${r['absolute_estimation_error']:.3f}.
    This answer is used only after fitting. It is unavailable in real launch data.</p>
  </details>
</section>"""


STYLE = """
*{box-sizing:border-box}body{margin:0;background:#fff;color:#252a2d;font:15px/1.55 system-ui,sans-serif}
main{max-width:940px;margin:0 auto;padding:30px 32px 50px}header{border-bottom:1px solid #b8bfbd;padding-bottom:20px}
.byline,.unit,.small,footer{font-size:12px;color:#596260}.byline{margin:0 0 9px}h1{font:600 36px/1.2 Georgia,serif;margin:0 0 14px;letter-spacing:-.6px}
h2{font-size:21px;line-height:1.3;margin:25px 0 10px}h3{font-size:14px;margin:18px 0 6px}p{margin:8px 0 13px;max-width:790px}
a{color:#235c70;text-underline-offset:3px}nav{display:flex;gap:22px;flex-wrap:wrap;margin:18px 0 23px}
button{font:inherit;color:#5e6764;padding:6px 0;background:none;border:0;border-bottom:2px solid transparent;cursor:pointer}
button[aria-pressed=true]{color:#1d2825;border-color:#1d2825;font-weight:650}.two-columns{display:grid;grid-template-columns:1fr 1fr;gap:34px}
table{border-collapse:collapse;width:100%;margin:8px 0 12px}td{padding:8px 0;border-bottom:1px solid #e0e4e1}td:last-child{text-align:right;font-variant-numeric:tabular-nums;padding-left:14px}
.accounting tr:last-child{font-weight:700;border-top:1px solid #667570}.accounting tr:last-child td{padding-top:12px}
.checks{font-size:13px}.checks td{padding:9px 0}.status{font-size:13px;font-weight:650}.legend{display:flex;gap:20px;font-size:12px}
.legend span:before{content:'';display:inline-block;width:19px;height:2px;margin:0 6px 4px 0;background:#a3482c}.legend span:last-child:before{background:#27677a}
svg{width:100%;height:auto}details{border-top:1px solid #d5dcd8;margin-top:17px;padding-top:13px;font-size:13px}summary{cursor:pointer;font-weight:600}
.sensitivity{border-top:1px solid #b8bfbd;margin-top:23px;padding-top:5px}input{display:block;width:100%;max-width:520px;margin:12px 0}
output{font-variant-numeric:tabular-nums}footer{border-top:1px solid #b8bfbd;margin-top:25px;padding-top:13px}.assumptions{font-size:13px}
@media(max-width:650px){main{padding:22px 18px}.two-columns{grid-template-columns:1fr;gap:3px}h1{font-size:30px}nav{gap:18px}.unit{max-width:280px}}
"""

SCRIPT = """
const DATA = __DATA__;
let active = 'migration';
const money = n => (n >= 0 ? '+' : '−') + '$' + Math.abs(n).toFixed(2);
function updateBias() {
  const result = DATA.find(row => row.scenario === active);
  const bias = Number(document.getElementById('bias').value);
  const shift = bias * 4.5;
  document.getElementById('bias-value').value = '$' + bias.toFixed(2);
  document.getElementById('adjusted').textContent =
    'Adjusted estimate: ' + money(result.cohort_did - shift) + '. Interval: ' +
    money(result.bootstrap_95_interval[0] - shift) + ' to ' +
    money(result.bootstrap_95_interval[1] - shift) + '.' +
    (result.identification_checks_pass ? '' : ' The comparison still fails its checks.');
}
document.querySelectorAll('[data-case]').forEach(button => {
  button.addEventListener('click', () => {
    active = button.dataset.case;
    document.querySelectorAll('.case').forEach(section => section.hidden = section.id !== active);
    document.querySelectorAll('[data-case]').forEach(tab => tab.setAttribute('aria-pressed', tab === button));
    updateBias();
  });
});
document.getElementById('bias').addEventListener('input', updateBias);
document.querySelector('[data-case="migration"]').click();
"""


def render(results, out):
    buttons = "".join(
        f'<button data-case="{r["scenario"]}" aria-pressed="false">{html.escape(r["label"])}</button>'
        for r in sorted(
            results,
            key=lambda r: ["migration", "growth", "broken_comparison"].index(
                r["scenario"]
            ),
        )
    )
    embedded = [
        {
            key: r[key]
            for key in [
                "scenario",
                "cohort_did",
                "bootstrap_95_interval",
                "identification_checks_pass",
            ]
        }
        for r in results
    ]
    page = f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Did it grow? A launch review</title><style>{STYLE}</style>
<main>
<header>
  <p class="byline">Raja Hasan / Launch measurement / November 2026</p>
  <h1>Did it grow, or did customers move?</h1>
  <p>A review of a fictional offer launched in two waves. The outcome includes both
  the new offer and the existing product, less the added service cost.</p>
  <p class="small"><strong>Simulated data.</strong> 40 markets, 40 weeks, 64,000 ledger records.
  No Intuit data or estimate of its performance.</p>
  <p class="small"><a href="https://github.com/rhasan55/did-it-grow">Code</a> / <a href="panel.sql">SQL</a> /
  <a href="methods.md">Methods</a> / <a href="sources.md">Public context</a></p>
</header>
<nav aria-label="Choose a case">{buttons}</nav>
{''.join(case_section(result) for result in results)}
<div class="sensitivity">
  <h3>Try a different assumption</h3>
  <label for="bias">Suppose rollout markets had an unmeasured extra upward trend of
  <output id="bias-value">$0.00</output> per customer per week.</label>
  <input id="bias" type="range" min="0" max="2" step="0.05" value="0">
  <p id="adjusted" aria-live="polite"></p>
  <p class="small">Subtracts the assumed trend × 4.5, the mean distance from the baseline
  week to the outcome weeks. This is a bias calculation, not a formal sensitivity bound.</p>
</div>
<h3>Before using this on a real launch</h3>
<p class="assumptions">Find genuinely unaffected controls. Check for changes in pricing,
marketing, eligibility and customer identity across products. Passing pre-launch checks
cannot rule out a new shock at rollout. If the offer is national or spills into the control
markets, this design may not be available.</p>
<footer>The SQL resolves duplicate deliveries and refund corrections before estimating effects.
<a href="test-results.txt">Tests</a> / <a href="analysis-audit.md">Analysis checks</a>.
Run <code>python analysis.py</code> to reproduce the report.</footer>
</main><script>{SCRIPT.replace('__DATA__',json.dumps(embedded))}</script></html>"""
    (out / "index.html").write_text(page)
    for r in results:
        (out / f'{r["scenario"]}.svg').write_text(chart_svg(r))
    r = next(r for r in results if r["scenario"] == "migration")
    (out / "preview.svg").write_text(
        f"""<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="440" viewBox="0 0 1000 440">
<rect width="1000" height="440" fill="white"/>
<g fill="#252a2d" font-family="sans-serif">
<text x="48" y="42" font-size="14">RAJA HASAN / LAUNCH REVIEW / SIMULATED DATA</text>
<text x="48" y="100" font-family="Georgia,serif" font-size="38">The offer grew. Combined contribution fell.</text>
<text x="48" y="142" font-size="17">Estimated weekly change per baseline-eligible customer</text>
<path d="M48,166H952" stroke="#8b9992"/>
<text x="48" y="207" font-size="19">New offer revenue</text><text x="940" y="207" text-anchor="end" font-size="24">{money(r['new_offer_lift'])}</text>
<text x="48" y="253" font-size="19">Existing product revenue</text><text x="940" y="253" text-anchor="end" font-size="24">{money(r['existing_product_change'])}</text>
<text x="48" y="299" font-size="19">Added service cost</text><text x="940" y="299" text-anchor="end" font-size="24">{money(r['contribution_lift']-r['net_revenue_lift'])}</text>
<path d="M48,322H952" stroke="#8b9992"/>
<text x="48" y="365" font-size="20" font-weight="700">Combined contribution</text><text x="940" y="365" text-anchor="end" font-size="28" font-weight="700">{money(r['cohort_did'])}</text>
<text x="48" y="415" font-size="13">Cohort DiD vs never-treated markets. Illustrative costs. Not full profit or an Intuit result.</text>
</g></svg>"""
    )
