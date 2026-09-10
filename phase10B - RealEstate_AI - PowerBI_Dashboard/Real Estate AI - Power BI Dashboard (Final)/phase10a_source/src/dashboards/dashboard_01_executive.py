"""Phase 10A, Section 10.3 -- Dashboard 1: Executive Overview."""
import json
import os
import sys

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _HERE)
from shell import shell

MARTS = os.path.join(_ROOT, "data_marts")
OUT = os.path.join(_ROOT, "dashboards")


def build():
    kpis = pd.read_csv(os.path.join(MARTS, "mart_01_portfolio_kpis.csv")).iloc[0]
    market = pd.read_csv(os.path.join(MARTS, "mart_02_market_locality.csv"))
    decision = pd.read_csv(os.path.join(MARTS, "mart_06_decision_summary.csv"))

    decision_counts = decision["decision"].value_counts().reindex(
        ["INVEST", "HOLD", "AVOID", "INSUFFICIENT"]).fillna(0).astype(int)
    top_localities = market.nlargest(6, "latest_demand_index")[["locality_name", "city_name",
                                                                    "latest_demand_index", "location_score"]]

    kpi_html = f"""
    <div class="kpi-row">
      <div class="kpi"><div class="label">Total properties in platform</div>
        <div class="value">{int(kpis['total_properties_in_platform']):,}</div></div>
      <div class="kpi"><div class="label">Localities tracked</div>
        <div class="value">{int(kpis['total_localities'])}</div><div class="delta">across {int(kpis['total_cities'])} cities</div></div>
      <div class="kpi"><div class="label">Properties fully evaluated</div>
        <div class="value">{int(kpis['properties_with_full_decision_evaluation'])}</div>
        <div class="delta">demo batch, full agent pipeline</div></div>
      <div class="kpi"><div class="label">Portfolio with full financial data</div>
        <div class="value">{kpis['pct_portfolio_with_full_observed_financial_data']:.1f}%</div>
        <div class="delta">expense + rental history present</div></div>
      <div class="kpi"><div class="label">Mean decision score</div>
        <div class="value">{kpis['mean_decision_score']:.1f}<span style="font-size:14px;color:var(--text-3)">/100</span></div></div>
      <div class="kpi"><div class="label">Mean decision confidence</div>
        <div class="value">{kpis['mean_decision_confidence']:.1f}<span style="font-size:14px;color:var(--text-3)">/100</span></div>
        <div class="delta">capped — Phase 7 risk is UNCALIBRATED</div></div>
    </div>
    """

    body = kpi_html + f"""
    <div class="grid cols-2">
      <div class="panel">
        <h3>Investment Decision Distribution</h3>
        <div class="panel-sub">Evaluated properties, by decision (Phase 9)</div>
        <canvas id="decisionChart"></canvas>
      </div>
      <div class="panel">
        <h3>Top Localities by Demand</h3>
        <div class="panel-sub">Latest demand index, top 6 of 90 localities</div>
        <canvas id="demandChart"></canvas>
      </div>
    </div>

    <div class="panel">
      <h3>Alerts &amp; Notable Findings</h3>
      <div class="panel-sub">Carried forward from Phase 6/7/8/9 build reports — not generated here</div>
      <table>
        <tr><th>Phase</th><th>Finding</th><th>Status</th></tr>
        <tr><td>Phase 6 — Financial</td><td>13 of 90 localities have an unreliable historical price CAGR (&gt;20%/yr), inherited from a Phase 3 data-generator bug — excluded from default appreciation assumptions</td><td><span class="badge limitations">FLAGGED</span></td></tr>
        <tr><td>Phase 7 — Risk</td><td>Appreciation assumption dominates simulated IRR risk (mean correlation +0.999) across the entire demo batch</td><td><span class="badge uncalibrated">UNCALIBRATED</span></td></tr>
        <tr><td>Phase 8 — Geo</td><td>Flood / environmental risk data does not exist anywhere in this platform — correctly reported as unavailable for all 90 localities, never estimated</td><td><span class="badge insufficientdata">NO DATA</span></td></tr>
        <tr><td>Phase 9 — Decision</td><td>Decision confidence cannot currently exceed ~82/100 for any property, because risk_completeness is permanently capped (Phase 7 is UNCALIBRATED)</td><td><span class="badge limitations">BY DESIGN</span></td></tr>
      </table>
    </div>

    <div class="note">This dashboard mockup renders <code>data_marts/mart_01_portfolio_kpis.csv</code> and <code>mart_02_market_locality.csv</code> directly — no metric on this page is calculated in this file.</div>
    """

    decision_data = json.dumps(decision_counts.tolist())
    demand_labels = json.dumps(top_localities["locality_name"].tolist())
    demand_values = json.dumps(top_localities["latest_demand_index"].tolist())

    script = f"""
    <script>
    new Chart(document.getElementById('decisionChart'), {{
      type: 'doughnut',
      data: {{ labels: ['INVEST','HOLD','AVOID','INSUFFICIENT'], datasets: [{{
        data: {decision_data}, backgroundColor: ['#4FAE84','#D9A85C','#D9695C','#5D6B7C'], borderWidth: 0 }}] }},
      options: {{ plugins: {{ legend: {{ position: 'bottom', labels: {{ color: '#93A2B3', boxWidth: 12 }} }} }} }}
    }});
    new Chart(document.getElementById('demandChart'), {{
      type: 'bar',
      data: {{ labels: {demand_labels}, datasets: [{{ data: {demand_values}, backgroundColor: '#D9A85C' }}] }},
      options: {{ indexAxis: 'y', plugins: {{ legend: {{ display: false }} }},
        scales: {{ x: {{ ticks: {{ color: '#93A2B3' }}, grid: {{ color: '#263140' }} }},
                   y: {{ ticks: {{ color: '#93A2B3' }}, grid: {{ display: false }} }} }} }}
    }});
    </script>
    """

    html = shell("index.html", "Dashboard 1 — Executive Overview",
                  "Real Estate AI Decision Intelligence Platform · Power BI data mart mockup",
                  body + script)
    with open(os.path.join(OUT, "index.html"), "w") as f:
        f.write(html)
    print("Wrote index.html")


if __name__ == "__main__":
    build()
