"""Phase 10A, Section 10.6 -- Dashboard 4: Financial & Risk Intelligence."""
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
    df = pd.read_csv(os.path.join(MARTS, "mart_04_financial_risk.csv"))
    scen4 = pd.read_csv(os.path.join(MARTS, "mart_04c_scenarios_extended4.csv"))

    scen_means = scen4.groupby("scenario")["irr"].mean().reindex(
        ["Severe Downside", "Downside", "Base", "Upside"])

    rows_html = "".join(f"""
      <tr><td>{r.property_id}</td><td>{r.locality_name}</td>
      <td class="num">{r.cap_rate*100:.2f}%</td><td class="num">{r.irr*100:.2f}%</td>
      <td class="num">₹{r.npv:,.0f}</td>
      <td class="num">{'%.2f' % r.dscr if pd.notna(r.dscr) else '—'}</td>
      <td class="num">{r.probability_negative_npv*100:.0f}%</td>
      <td class="num">₹{r.var_95_npv:,.0f}</td></tr>
    """ for r in df.itertuples())

    kpi_html = f"""
    <div class="kpi-row">
      <div class="kpi"><div class="label">Median cap rate</div><div class="value">{df['cap_rate'].median()*100:.2f}%</div></div>
      <div class="kpi"><div class="label">Median IRR (Base)</div><div class="value">{df['irr'].median()*100:.2f}%</div></div>
      <div class="kpi"><div class="label">Median NPV (Base)</div><div class="value">₹{df['npv'].median():,.0f}</div></div>
      <div class="kpi"><div class="label">Mean P(negative NPV)</div>
        <div class="value neg">{df['probability_negative_npv'].mean()*100:.0f}%</div>
        <div class="delta">Monte Carlo — UNCALIBRATED</div></div>
    </div>
    """

    body = kpi_html + f"""
    <div class="grid cols-2">
      <div class="panel"><h3>IRR by Scenario</h3><div class="panel-sub">Mean across demo batch — Severe Downside / Downside / Base / Upside</div>
        <canvas id="scenChart"></canvas></div>
      <div class="panel"><h3>Cap Rate vs. IRR</h3><div class="panel-sub">Each point: one property, Base case</div>
        <canvas id="capIrr"></canvas></div>
    </div>
    <div class="grid cols-2">
      <div class="panel"><h3>NPV Distribution (Base case)</h3>
        <canvas id="npvHist"></canvas></div>
      <div class="panel"><h3>Probability of Negative NPV</h3><div class="panel-sub">Per property, Monte Carlo simulated — not a real-world probability</div>
        <canvas id="probNeg"></canvas></div>
    </div>
    <div class="panel">
      <h3>Financial &amp; Risk Detail</h3>
      <table><tr><th>ID</th><th>Locality</th><th>Cap Rate</th><th>IRR</th><th>NPV</th><th>DSCR</th><th>P(neg NPV)</th><th>VaR 95%</th></tr>
      {rows_html}</table>
    </div>
    <div class="note"><strong>UNCALIBRATED:</strong> every probability/VaR/CVaR figure on this page comes from Phase 7's Monte Carlo engine, whose distribution bounds are documented judgement calls, not fitted to real historical outcomes. Source: <code>mart_04_financial_risk.csv</code>, <code>mart_04c_scenarios_extended4.csv</code>.</div>
    """

    npv_bins = pd.cut(df["npv"], bins=8)
    npv_counts = npv_bins.value_counts().sort_index()
    npv_labels = [f"₹{iv.left/1e6:.1f}M" for iv in npv_counts.index]

    script = f"""
    <script>
    new Chart(document.getElementById('scenChart'), {{ type: 'bar',
      data: {{ labels: {json.dumps(scen_means.index.tolist())},
        datasets: [{{ data: {json.dumps([round(v*100,2) if pd.notna(v) else None for v in scen_means.tolist()])},
        backgroundColor: ['#D9695C','#D9A85C','#5B9BD9','#4FAE84'] }}] }},
      options: {{ plugins: {{ legend: {{ display: false }} }},
        scales: {{ y: {{ title: {{ display: true, text: 'IRR (%)', color: '#93A2B3' }}, ticks: {{ color: '#93A2B3' }}, grid: {{ color: '#263140' }} }},
                   x: {{ ticks: {{ color: '#93A2B3' }}, grid: {{ display: false }} }} }} }} }});
    new Chart(document.getElementById('capIrr'), {{ type: 'scatter',
      data: {{ datasets: [{{ data: {json.dumps([{"x": round(r.cap_rate*100,2), "y": round(r.irr*100,2)} for r in df.itertuples()])},
        backgroundColor: '#D9A85C' }}] }},
      options: {{ plugins: {{ legend: {{ display: false }} }},
        scales: {{ x: {{ title: {{ display: true, text: 'Cap Rate (%)', color: '#93A2B3' }}, ticks: {{ color: '#93A2B3' }}, grid: {{ color: '#263140' }} }},
                   y: {{ title: {{ display: true, text: 'IRR (%)', color: '#93A2B3' }}, ticks: {{ color: '#93A2B3' }}, grid: {{ color: '#263140' }} }} }} }} }});
    new Chart(document.getElementById('npvHist'), {{ type: 'bar',
      data: {{ labels: {json.dumps(npv_labels)}, datasets: [{{ data: {json.dumps(npv_counts.tolist())}, backgroundColor: '#5B9BD9' }}] }},
      options: {{ plugins: {{ legend: {{ display: false }} }},
        scales: {{ y: {{ ticks: {{ color: '#93A2B3' }}, grid: {{ color: '#263140' }} }}, x: {{ ticks: {{ color: '#93A2B3' }}, grid: {{ display: false }} }} }} }} }});
    new Chart(document.getElementById('probNeg'), {{ type: 'bar',
      data: {{ labels: {json.dumps([str(int(x)) for x in df['property_id'].tolist()])},
        datasets: [{{ data: {json.dumps([round(v*100,1) for v in df['probability_negative_npv'].tolist()])}, backgroundColor: '#D9695C' }}] }},
      options: {{ plugins: {{ legend: {{ display: false }} }},
        scales: {{ y: {{ title: {{ display: true, text: '% of simulations', color: '#93A2B3' }}, ticks: {{ color: '#93A2B3' }}, grid: {{ color: '#263140' }} }},
                   x: {{ ticks: {{ color: '#93A2B3', maxRotation: 90 }}, grid: {{ display: false }} }} }} }} }});
    </script>
    """

    html = shell("dashboard_04_financial_risk.html", "Dashboard 4 — Financial & Risk Intelligence",
                  "ROI, IRR, NPV, NOI, yield, DSCR, scenarios, sensitivity, Monte Carlo",
                  body + script)
    with open(os.path.join(OUT, "dashboard_04_financial_risk.html"), "w") as f:
        f.write(html)
    print("Wrote dashboard_04_financial_risk.html")


if __name__ == "__main__":
    build()
