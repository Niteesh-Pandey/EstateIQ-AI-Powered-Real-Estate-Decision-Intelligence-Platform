"""Phase 10A, Section 10.5 -- Dashboard 3: Property & Investment Analysis."""
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


def badge(decision):
    cls = decision.lower() if isinstance(decision, str) else "insufficient"
    return f'<span class="badge {cls}">{decision}</span>'


def build():
    df = pd.read_csv(os.path.join(MARTS, "mart_03_property_investment.csv"))
    df_gap = df.dropna(subset=["valuation_gap_pct"])

    rows_html = "".join(f"""
      <tr><td>{r.property_id}</td><td>{r.locality_name}</td><td>{r.property_type}</td>
      <td class="num">₹{r.asking_price:,.0f}</td>
      <td class="num">{'₹%s' % format(r.predicted_valuation, ',.0f') if pd.notna(r.predicted_valuation) else '—'}</td>
      <td class="num">{'%+.1f%%' % r.valuation_gap_pct if pd.notna(r.valuation_gap_pct) else '—'}</td>
      <td class="num">{'₹%s' % format(r.predicted_rent, ',.0f') if pd.notna(r.predicted_rent) else '—'}</td>
      <td>{badge(r.decision)}</td></tr>
    """ for r in df.itertuples())

    kpi_html = f"""
    <div class="kpi-row">
      <div class="kpi"><div class="label">Properties evaluated</div><div class="value">{len(df)}</div></div>
      <div class="kpi"><div class="label">With model valuation</div><div class="value">{df['predicted_valuation'].notna().sum()}</div>
        <div class="delta">valuation_v1_gbr — PASS WITH LIMITATIONS tier</div></div>
      <div class="kpi"><div class="label">Median valuation gap</div>
        <div class="value">{df_gap['valuation_gap_pct'].median():+.1f}%</div>
        <div class="delta">predicted vs. asking price</div></div>
      <div class="kpi"><div class="label">Undervalued (gap &gt; +5%)</div>
        <div class="value pos">{(df_gap['valuation_gap_pct'] > 5).sum()}</div></div>
    </div>
    """

    body = kpi_html + f"""
    <div class="grid cols-2">
      <div class="panel"><h3>Predicted Valuation vs. Asking Price</h3>
        <div class="panel-sub">Each point: one property. Above the line = model thinks it's underpriced.</div>
        <canvas id="valScatter"></canvas></div>
      <div class="panel"><h3>Valuation Gap Distribution</h3>
        <div class="panel-sub">(predicted − asking) / asking, %</div>
        <canvas id="gapHist"></canvas></div>
    </div>
    <div class="panel">
      <h3>Property Comparables Table</h3>
      <div class="panel-sub">Model A (valuation) and Model B (rent) — both PASS WITH LIMITATIONS per Phase 4 registry. DOM and sale-probability models are REJECTED and never shown here.</div>
      <table><tr><th>ID</th><th>Locality</th><th>Type</th><th>Asking Price</th><th>Predicted Value</th><th>Gap</th><th>Predicted Rent</th><th>Decision</th></tr>
      {rows_html}</table>
    </div>
    <div class="note">Source: <code>mart_03_property_investment.csv</code>. Predictions from Phase 4's trained <code>valuation_v1_gbr.joblib</code> / <code>rent_v1_gbr.joblib</code>, decisions from Phase 9. No REJECTED model (days-on-market, sale probability) is used anywhere on this page.</div>
    """

    scatter_data = [{"x": r.asking_price, "y": r.predicted_valuation} for r in df.itertuples()
                     if pd.notna(r.predicted_valuation)]
    gap_bins = pd.cut(df_gap["valuation_gap_pct"], bins=10)
    gap_counts = gap_bins.value_counts().sort_index()
    gap_labels = [f"{iv.left:.0f}%" for iv in gap_counts.index]

    script = f"""
    <script>
    new Chart(document.getElementById('valScatter'), {{ type: 'scatter',
      data: {{ datasets: [{{ label: 'Properties', data: {json.dumps(scatter_data)}, backgroundColor: '#D9A85C' }},
        {{ label: 'Fair value line', type: 'line', data: {json.dumps(
            [{"x": mn, "y": mn} for mn in [df['asking_price'].min(), df['asking_price'].max()]])},
           borderColor: '#5D6B7C', borderDash: [4,4], pointRadius: 0 }}] }},
      options: {{ plugins: {{ legend: {{ labels: {{ color: '#93A2B3' }} }} }},
        scales: {{ x: {{ title: {{ display: true, text: 'Asking Price (₹)', color: '#93A2B3' }}, ticks: {{ color: '#93A2B3' }}, grid: {{ color: '#263140' }} }},
                   y: {{ title: {{ display: true, text: 'Predicted Valuation (₹)', color: '#93A2B3' }}, ticks: {{ color: '#93A2B3' }}, grid: {{ color: '#263140' }} }} }} }} }});
    new Chart(document.getElementById('gapHist'), {{ type: 'bar',
      data: {{ labels: {json.dumps(gap_labels)}, datasets: [{{ data: {json.dumps(gap_counts.tolist())}, backgroundColor: '#5B9BD9' }}] }},
      options: {{ plugins: {{ legend: {{ display: false }} }},
        scales: {{ y: {{ ticks: {{ color: '#93A2B3' }}, grid: {{ color: '#263140' }} }}, x: {{ ticks: {{ color: '#93A2B3' }}, grid: {{ display: false }} }} }} }} }});
    </script>
    """

    html = shell("dashboard_03_property_investment.html", "Dashboard 3 — Property & Investment Analysis",
                  "Property details, comparables, and predicted value/rent",
                  body + script)
    with open(os.path.join(OUT, "dashboard_03_property_investment.html"), "w") as f:
        f.write(html)
    print("Wrote dashboard_03_property_investment.html")


if __name__ == "__main__":
    build()
