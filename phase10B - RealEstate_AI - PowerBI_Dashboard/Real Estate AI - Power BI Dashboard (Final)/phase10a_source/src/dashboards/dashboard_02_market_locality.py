"""Phase 10A, Section 10.4 -- Dashboard 2: Market & Locality Intelligence."""
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
    df = pd.read_csv(os.path.join(MARTS, "mart_02_market_locality.csv"))
    df = df.sort_values("demand_supply_rank")

    top_growth = df.nlargest(8, "yoy_price_growth_pct")[["locality_name", "yoy_price_growth_pct"]].dropna()
    bottom_growth = df.nsmallest(8, "yoy_price_growth_pct")[["locality_name", "yoy_price_growth_pct"]].dropna()
    city_demand = df.groupby("city_name")["latest_demand_index"].mean().sort_values(ascending=False)

    rows_html = "".join(f"""
      <tr><td>{r.locality_name}</td><td>{r.city_name}</td>
      <td class="num">{r.yoy_price_growth_pct:+.1f}%</td>
      <td class="num">{r.latest_demand_index:.1f}</td>
      <td class="num">{r.latest_supply_index:.1f}</td>
      <td class="num">{r.latest_absorption_rate:.2f}</td>
      <td class="num">{r.location_score:.1f}</td></tr>
    """ for r in df.head(20).itertuples())

    kpi_html = f"""
    <div class="kpi-row">
      <div class="kpi"><div class="label">Localities tracked</div><div class="value">{len(df)}</div></div>
      <div class="kpi"><div class="label">Median YoY price growth</div>
        <div class="value">{df['yoy_price_growth_pct'].median():+.1f}%</div></div>
      <div class="kpi"><div class="label">Median demand index</div>
        <div class="value">{df['latest_demand_index'].median():.1f}</div></div>
      <div class="kpi"><div class="label">Median absorption rate</div>
        <div class="value">{df['latest_absorption_rate'].median():.2f}</div></div>
    </div>
    """

    body = kpi_html + f"""
    <div class="grid cols-2">
      <div class="panel"><h3>Top Locality Growth (YoY)</h3><div class="panel-sub">Price-per-sqft, year-over-year</div>
        <canvas id="topGrowth"></canvas></div>
      <div class="panel"><h3>Bottom Locality Growth (YoY)</h3><div class="panel-sub">Price-per-sqft, year-over-year</div>
        <canvas id="bottomGrowth"></canvas></div>
    </div>
    <div class="grid cols-2">
      <div class="panel"><h3>Mean Demand Index by City</h3>
        <canvas id="cityDemand"></canvas></div>
      <div class="panel"><h3>Demand vs. Supply</h3><div class="panel-sub">All 90 localities</div>
        <canvas id="demandSupply"></canvas></div>
    </div>
    <div class="panel">
      <h3>Locality Ranking Table</h3><div class="panel-sub">Ranked by latest demand index, top 20 of 90</div>
      <table><tr><th>Locality</th><th>City</th><th>YoY Growth</th><th>Demand</th><th>Supply</th><th>Absorption</th><th>Location Score</th></tr>
      {rows_html}</table>
    </div>
    <div class="note">Source: <code>mart_02_market_locality.csv</code>, built from <code>core.market_monthly</code> using the same demand/supply/CAGR logic Phase 8 already tested — not recomputed differently here.</div>
    """

    script = f"""
    <script>
    new Chart(document.getElementById('topGrowth'), {{ type: 'bar',
      data: {{ labels: {json.dumps(top_growth['locality_name'].tolist())},
        datasets: [{{ data: {json.dumps(top_growth['yoy_price_growth_pct'].tolist())}, backgroundColor: '#4FAE84' }}] }},
      options: {{ indexAxis: 'y', plugins: {{ legend: {{ display: false }} }},
        scales: {{ x: {{ ticks: {{ color: '#93A2B3' }}, grid: {{ color: '#263140' }} }}, y: {{ ticks: {{ color: '#93A2B3' }}, grid: {{ display: false }} }} }} }} }});
    new Chart(document.getElementById('bottomGrowth'), {{ type: 'bar',
      data: {{ labels: {json.dumps(bottom_growth['locality_name'].tolist())},
        datasets: [{{ data: {json.dumps(bottom_growth['yoy_price_growth_pct'].tolist())}, backgroundColor: '#D9695C' }}] }},
      options: {{ indexAxis: 'y', plugins: {{ legend: {{ display: false }} }},
        scales: {{ x: {{ ticks: {{ color: '#93A2B3' }}, grid: {{ color: '#263140' }} }}, y: {{ ticks: {{ color: '#93A2B3' }}, grid: {{ display: false }} }} }} }} }});
    new Chart(document.getElementById('cityDemand'), {{ type: 'bar',
      data: {{ labels: {json.dumps(city_demand.index.tolist())},
        datasets: [{{ data: {json.dumps([round(v,1) for v in city_demand.tolist()])}, backgroundColor: '#5B9BD9' }}] }},
      options: {{ plugins: {{ legend: {{ display: false }} }},
        scales: {{ y: {{ ticks: {{ color: '#93A2B3' }}, grid: {{ color: '#263140' }} }}, x: {{ ticks: {{ color: '#93A2B3' }}, grid: {{ display: false }} }} }} }} }});
    new Chart(document.getElementById('demandSupply'), {{ type: 'scatter',
      data: {{ datasets: [{{ data: {json.dumps([{"x": r.latest_supply_index, "y": r.latest_demand_index} for r in df.itertuples()])},
        backgroundColor: '#D9A85C' }}] }},
      options: {{ plugins: {{ legend: {{ display: false }} }},
        scales: {{ x: {{ title: {{ display: true, text: 'Supply Index', color: '#93A2B3' }}, ticks: {{ color: '#93A2B3' }}, grid: {{ color: '#263140' }} }},
                   y: {{ title: {{ display: true, text: 'Demand Index', color: '#93A2B3' }}, ticks: {{ color: '#93A2B3' }}, grid: {{ color: '#263140' }} }} }} }} }});
    </script>
    """

    html = shell("dashboard_02_market_locality.html", "Dashboard 2 — Market & Locality Intelligence",
                  "Price trends, growth, demand/supply, and locality ranking",
                  body + script)
    with open(os.path.join(OUT, "dashboard_02_market_locality.html"), "w") as f:
        f.write(html)
    print("Wrote dashboard_02_market_locality.html")


if __name__ == "__main__":
    build()
