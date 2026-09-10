"""Phase 10A, Section 10.8 -- Dashboard 6: Decision Intelligence."""
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


def badge(v):
    return f'<span class="badge {v.lower()}">{v}</span>'


def build():
    summary = pd.read_csv(os.path.join(MARTS, "mart_06_decision_summary.csv"))
    components = pd.read_csv(os.path.join(MARTS, "mart_06b_decision_components.csv"))
    reasons = pd.read_csv(os.path.join(MARTS, "mart_06d_decision_reasons.csv"))

    counts = summary["decision"].value_counts().reindex(["INVEST", "HOLD", "AVOID", "INSUFFICIENT"]).fillna(0)
    comp_means = components.groupby("component")["score"].mean().sort_values()

    rows_html = "".join(f"""
      <tr><td>{r.property_id}</td><td>{badge(r.decision)}</td>
      <td class="num">{'%.1f' % r.decision_score if pd.notna(r.decision_score) else '—'}</td>
      <td class="num">{r.decision_confidence:.1f}</td>
      <td>{r.data_quality_status}</td><td>{r.model_status}</td><td>{r.evidence_status}</td></tr>
    """ for r in summary.itertuples())

    top_risks = reasons[reasons["type"] == "risk"]["text"].value_counts().head(6)

    kpi_html = f"""
    <div class="kpi-row">
      <div class="kpi"><div class="label">INVEST</div><div class="value pos">{int(counts['INVEST'])}</div></div>
      <div class="kpi"><div class="label">HOLD</div><div class="value" style="color:var(--warn)">{int(counts['HOLD'])}</div></div>
      <div class="kpi"><div class="label">AVOID</div><div class="value neg">{int(counts['AVOID'])}</div></div>
      <div class="kpi"><div class="label">INSUFFICIENT</div><div class="value" style="color:var(--text-3)">{int(counts['INSUFFICIENT'])}</div></div>
      <div class="kpi"><div class="label">Mean decision score</div><div class="value">{summary['decision_score'].dropna().mean():.1f}</div></div>
      <div class="kpi"><div class="label">Mean confidence</div><div class="value">{summary['decision_confidence'].mean():.1f}</div>
        <div class="delta">ceiling ~82 — Phase 7 risk is UNCALIBRATED</div></div>
    </div>
    """

    body = kpi_html + f"""
    <div class="grid cols-2">
      <div class="panel"><h3>Decision Distribution</h3>
        <canvas id="decDist"></canvas></div>
      <div class="panel"><h3>Mean Component Score</h3><div class="panel-sub">Market / Prediction / Financial / Risk / Geo — 0-100</div>
        <canvas id="compScores"></canvas></div>
    </div>
    <div class="panel">
      <h3>Score vs. Confidence</h3>
      <div class="panel-sub">Gate lines: INVEST needs score ≥65 AND confidence ≥55. A high score with low confidence downgrades to HOLD, not INVEST.</div>
      <canvas id="scoreConf" style="max-height:340px"></canvas>
    </div>
    <div class="grid cols-2">
      <div class="panel">
        <h3>Most Common Key Risks</h3><div class="panel-sub">Across the demo batch</div>
        <table><tr><th>Risk</th><th>Count</th></tr>
        {"".join(f'<tr><td>{k[:80]}</td><td class="num">{v}</td></tr>' for k,v in top_risks.items())}</table>
      </div>
      <div class="panel">
        <h3>All Decisions</h3>
        <table><tr><th>ID</th><th>Decision</th><th>Score</th><th>Confidence</th><th>Data</th><th>Model</th><th>Evidence</th></tr>
        {rows_html}</table>
      </div>
    </div>
    <div class="note">Source: <code>mart_06_decision_summary.csv</code>, <code>mart_06b_decision_components.csv</code>, <code>mart_06d_decision_reasons.csv</code> — Phase 9's deterministic Decision Policy output, unmodified. No decision on this page was made by an LLM.</div>
    """

    scatter = [{"x": r.decision_score, "y": r.decision_confidence, "label": r.decision}
               for r in summary.itertuples() if pd.notna(r.decision_score)]
    colors = {"INVEST": "#4FAE84", "HOLD": "#D9A85C", "AVOID": "#D9695C", "INSUFFICIENT": "#5D6B7C"}
    datasets = []
    for label, color in colors.items():
        pts = [p for p in scatter if p["label"] == label]
        if pts:
            datasets.append(f"{{ label: '{label}', data: {json.dumps([{'x':p['x'],'y':p['y']} for p in pts])}, backgroundColor: '{color}' }}")

    script = f"""
    <script>
    new Chart(document.getElementById('decDist'), {{ type: 'doughnut',
      data: {{ labels: ['INVEST','HOLD','AVOID','INSUFFICIENT'],
        datasets: [{{ data: {json.dumps(counts.tolist())}, backgroundColor: ['#4FAE84','#D9A85C','#D9695C','#5D6B7C'], borderWidth: 0 }}] }},
      options: {{ plugins: {{ legend: {{ position: 'bottom', labels: {{ color: '#93A2B3', boxWidth: 12 }} }} }} }} }});
    new Chart(document.getElementById('compScores'), {{ type: 'bar',
      data: {{ labels: {json.dumps(comp_means.index.tolist())},
        datasets: [{{ data: {json.dumps([round(v,1) for v in comp_means.tolist()])}, backgroundColor: '#5B9BD9' }}] }},
      options: {{ indexAxis: 'y', plugins: {{ legend: {{ display: false }} }},
        scales: {{ x: {{ ticks: {{ color: '#93A2B3' }}, grid: {{ color: '#263140' }} }}, y: {{ ticks: {{ color: '#93A2B3' }}, grid: {{ display: false }} }} }} }} }});
    new Chart(document.getElementById('scoreConf'), {{ type: 'scatter',
      data: {{ datasets: [{','.join(datasets)}] }},
      options: {{ plugins: {{ legend: {{ labels: {{ color: '#93A2B3' }} }} }},
        scales: {{ x: {{ min: 0, max: 100, title: {{ display: true, text: 'Decision Score', color: '#93A2B3' }}, ticks: {{ color: '#93A2B3' }}, grid: {{ color: '#263140' }} }},
                   y: {{ min: 0, max: 100, title: {{ display: true, text: 'Decision Confidence', color: '#93A2B3' }}, ticks: {{ color: '#93A2B3' }}, grid: {{ color: '#263140' }} }} }} }} }});
    </script>
    """

    html = shell("dashboard_06_decision.html", "Dashboard 6 — Decision Intelligence",
                  "INVEST / HOLD / AVOID / INSUFFICIENT, score, confidence, reasons, risks",
                  body + script)
    with open(os.path.join(OUT, "dashboard_06_decision.html"), "w") as f:
        f.write(html)
    print("Wrote dashboard_06_decision.html")


if __name__ == "__main__":
    build()
