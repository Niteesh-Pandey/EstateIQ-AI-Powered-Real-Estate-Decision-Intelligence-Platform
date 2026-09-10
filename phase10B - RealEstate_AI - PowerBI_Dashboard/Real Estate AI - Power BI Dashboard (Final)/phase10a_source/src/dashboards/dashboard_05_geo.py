"""Phase 10A, Section 10.7 -- Dashboard 5: Geo Intelligence."""
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
    df = pd.read_csv(os.path.join(MARTS, "mart_05_geo.csv"))

    top20 = df.nlargest(20, "location_score")

    rows_html = "".join(f"""
      <tr><td>{r.locality_name}</td><td>{r.city}</td>
      <td class="num">{r.location_score:.1f}</td><td class="num">{r.accessibility_score:.1f}</td>
      <td class="num">{int(r.total_items)}</td>
      <td class="num">{'%.1f' % r.infrastructure_delivery_risk_score if pd.notna(r.infrastructure_delivery_risk_score) else '—'}</td>
      <td class="num">{'%.1f' % r.infrastructure_concentration_risk_score if pd.notna(r.infrastructure_concentration_risk_score) else '—'}</td>
      <td><span class="badge insufficientdata">{r.flood_risk_status}</span></td></tr>
    """ for r in top20.itertuples())

    kpi_html = f"""
    <div class="kpi-row">
      <div class="kpi"><div class="label">Localities scored</div><div class="value">{len(df)}</div></div>
      <div class="kpi"><div class="label">Mean location score</div><div class="value">{df['location_score'].mean():.1f}</div></div>
      <div class="kpi"><div class="label">Full coverage (PASS)</div>
        <div class="value">{(df['validation_status']=='PASS').sum()}<span style="font-size:14px;color:var(--text-3)">/{len(df)}</span></div></div>
      <div class="kpi"><div class="label">Flood/environmental data available</div>
        <div class="value neg">{(df['flood_risk_status']!='INSUFFICIENT DATA').sum()}<span style="font-size:14px;color:var(--text-3)">/{len(df)}</span></div>
        <div class="delta">no hazard data exists in this platform</div></div>
    </div>
    """

    body = kpi_html + f"""
    <div class="grid cols-2">
      <div class="panel"><h3>Location Score by City</h3>
        <canvas id="cityScore"></canvas></div>
      <div class="panel"><h3>Location Score vs. Accessibility</h3><div class="panel-sub">All 90 localities</div>
        <canvas id="scoreAccess"></canvas></div>
    </div>
    <div class="grid cols-2">
      <div class="panel"><h3>Infrastructure Delivery Risk</h3><div class="panel-sub">% of infra impact still "planned", proxy indicator</div>
        <canvas id="deliveryRisk"></canvas></div>
      <div class="panel"><h3>Infrastructure Concentration Risk</h3><div class="panel-sub">Herfindahl-style, single-point-of-failure exposure</div>
        <canvas id="concRisk"></canvas></div>
    </div>
    <div class="panel">
      <h3>Top 20 Localities by Location Score</h3>
      <table><tr><th>Locality</th><th>City</th><th>Location Score</th><th>Accessibility</th><th>Infra Items</th><th>Delivery Risk</th><th>Concentration Risk</th><th>Flood Risk</th></tr>
      {rows_html}</table>
    </div>
    <div class="note"><strong>flood_risk / environmental_risk = INSUFFICIENT DATA for all 90 localities.</strong> This platform has no hazard/climate data source — Phase 8's engine correctly refuses to estimate a substitute rather than inventing one. Source: <code>mart_05_geo.csv</code>.</div>
    """

    city_scores = df.groupby("city")["location_score"].mean().sort_values(ascending=False)
    delivery_bins = pd.cut(df["infrastructure_delivery_risk_score"].dropna(), bins=6)
    delivery_counts = delivery_bins.value_counts().sort_index()
    conc_bins = pd.cut(df["infrastructure_concentration_risk_score"].dropna(), bins=6)
    conc_counts = conc_bins.value_counts().sort_index()

    script = f"""
    <script>
    new Chart(document.getElementById('cityScore'), {{ type: 'bar',
      data: {{ labels: {json.dumps(city_scores.index.tolist())},
        datasets: [{{ data: {json.dumps([round(v,1) for v in city_scores.tolist()])}, backgroundColor: '#D9A85C' }}] }},
      options: {{ plugins: {{ legend: {{ display: false }} }},
        scales: {{ y: {{ ticks: {{ color: '#93A2B3' }}, grid: {{ color: '#263140' }} }}, x: {{ ticks: {{ color: '#93A2B3' }}, grid: {{ display: false }} }} }} }} }});
    new Chart(document.getElementById('scoreAccess'), {{ type: 'scatter',
      data: {{ datasets: [{{ data: {json.dumps([{"x": r.accessibility_score, "y": r.location_score} for r in df.itertuples() if pd.notna(r.accessibility_score)])},
        backgroundColor: '#5B9BD9' }}] }},
      options: {{ plugins: {{ legend: {{ display: false }} }},
        scales: {{ x: {{ title: {{ display: true, text: 'Accessibility Score', color: '#93A2B3' }}, ticks: {{ color: '#93A2B3' }}, grid: {{ color: '#263140' }} }},
                   y: {{ title: {{ display: true, text: 'Location Score', color: '#93A2B3' }}, ticks: {{ color: '#93A2B3' }}, grid: {{ color: '#263140' }} }} }} }} }});
    new Chart(document.getElementById('deliveryRisk'), {{ type: 'bar',
      data: {{ labels: {json.dumps([f"{iv.left:.0f}" for iv in delivery_counts.index])},
        datasets: [{{ data: {json.dumps(delivery_counts.tolist())}, backgroundColor: '#D9695C' }}] }},
      options: {{ plugins: {{ legend: {{ display: false }} }},
        scales: {{ y: {{ ticks: {{ color: '#93A2B3' }}, grid: {{ color: '#263140' }} }}, x: {{ ticks: {{ color: '#93A2B3' }}, grid: {{ display: false }} }} }} }} }});
    new Chart(document.getElementById('concRisk'), {{ type: 'bar',
      data: {{ labels: {json.dumps([f"{iv.left:.0f}" for iv in conc_counts.index])},
        datasets: [{{ data: {json.dumps(conc_counts.tolist())}, backgroundColor: '#D9A85C' }}] }},
      options: {{ plugins: {{ legend: {{ display: false }} }},
        scales: {{ y: {{ ticks: {{ color: '#93A2B3' }}, grid: {{ color: '#263140' }} }}, x: {{ ticks: {{ color: '#93A2B3' }}, grid: {{ display: false }} }} }} }} }});
    </script>
    """

    html = shell("dashboard_05_geo.html", "Dashboard 5 — Geo Intelligence",
                  "Location score, accessibility, infrastructure, geo risk",
                  body + script)
    with open(os.path.join(OUT, "dashboard_05_geo.html"), "w") as f:
        f.write(html)
    print("Wrote dashboard_05_geo.html")


if __name__ == "__main__":
    build()
