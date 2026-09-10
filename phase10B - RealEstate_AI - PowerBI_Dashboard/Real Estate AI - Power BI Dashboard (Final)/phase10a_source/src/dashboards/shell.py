"""
Shared design system for the Phase 10A dashboard mockups.

Design tokens (documented per frontend-design guidance):
  Base:      #0B0F14 (near-black slate, not pure black)
  Surface:   #131A22 (panel background)
  Surface-2: #182029 (nested panel / table stripe)
  Border:    #263140 (hairline, no drop shadows)
  Text:      #E7EDF3 (primary), #93A2B3 (secondary), #5D6B7C (tertiary/labels)
  Accent:    #D9A85C (warm brass/gold -- property & value)
  Accent-2:  #5B9BD9 (cool blue -- data series contrast)
  Positive:  #4FAE84   Negative: #D9695C   Warning: #D9A85C   Neutral: #5D6B7C

Typeface: IBM Plex Sans throughout (technical, precise numerals, no serif
mismatch) -- weight and size carry hierarchy instead of a second typeface.
No rounded-card-plus-shadow kit: panels are flat with a 1px hairline border
and a very slightly lighter fill than the base, no border-radius above 4px,
no box-shadow anywhere.
"""

BASE_CSS = """
:root {
  --bg: #0B0F14; --surface: #131A22; --surface-2: #182029; --border: #263140;
  --text: #E7EDF3; --text-2: #93A2B3; --text-3: #5D6B7C;
  --accent: #D9A85C; --accent-2: #5B9BD9;
  --pos: #4FAE84; --neg: #D9695C; --warn: #D9A85C; --neutral: #5D6B7C;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--text);
  font-family: 'IBM Plex Sans', -apple-system, sans-serif;
  font-size: 14px; line-height: 1.5;
}
.topbar {
  display: flex; align-items: baseline; justify-content: space-between;
  padding: 20px 32px; border-bottom: 1px solid var(--border);
  background: var(--surface);
}
.topbar h1 { font-size: 19px; font-weight: 600; margin: 0; letter-spacing: -0.01em; }
.topbar .subtitle { color: var(--text-2); font-size: 12.5px; margin-top: 3px; }
.topbar nav { display: flex; gap: 4px; }
.topbar nav a {
  color: var(--text-2); text-decoration: none; font-size: 12.5px; padding: 6px 11px;
  border: 1px solid var(--border); border-radius: 3px;
}
.topbar nav a.active { color: var(--bg); background: var(--accent); border-color: var(--accent); font-weight: 600; }
.topbar nav a:hover:not(.active) { color: var(--text); border-color: var(--text-3); }

.page { padding: 24px 32px 48px; max-width: 1360px; margin: 0 auto; }

.kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 1px;
  background: var(--border); border: 1px solid var(--border); margin-bottom: 28px; }
.kpi { background: var(--surface); padding: 18px 20px; }
.kpi .label { color: var(--text-3); font-size: 11.5px; margin-bottom: 8px; }
.kpi .value { font-size: 26px; font-weight: 600; letter-spacing: -0.01em; }
.kpi .value.pos { color: var(--pos); } .kpi .value.neg { color: var(--neg); }
.kpi .delta { font-size: 12px; color: var(--text-2); margin-top: 4px; }

.grid { display: grid; gap: 20px; margin-bottom: 24px; }
.grid.cols-2 { grid-template-columns: 1fr 1fr; }
.grid.cols-3 { grid-template-columns: 1fr 1fr 1fr; }
.grid.cols-4 { grid-template-columns: repeat(4, 1fr); }
@media (max-width: 980px) { .grid.cols-2, .grid.cols-3, .grid.cols-4 { grid-template-columns: 1fr; } }

.panel { background: var(--surface); border: 1px solid var(--border); padding: 18px 20px; }
.panel h3 { margin: 0 0 4px; font-size: 13.5px; font-weight: 600; }
.panel .panel-sub { color: var(--text-3); font-size: 11.5px; margin-bottom: 14px; }
.panel canvas { max-height: 280px; }

table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
th { text-align: left; color: var(--text-3); font-weight: 500; font-size: 11px;
     padding: 8px 10px; border-bottom: 1px solid var(--border); }
td { padding: 8px 10px; border-bottom: 1px solid var(--surface-2); color: var(--text-2); }
tr:hover td { background: var(--surface-2); color: var(--text); }
td.num { text-align: right; font-variant-numeric: tabular-nums; }
.badge { display: inline-block; padding: 2px 8px; font-size: 10.5px; font-weight: 600; border-radius: 3px; }
.badge.invest { background: rgba(79,174,132,0.15); color: var(--pos); }
.badge.hold { background: rgba(217,168,92,0.15); color: var(--warn); }
.badge.avoid { background: rgba(217,105,92,0.15); color: var(--neg); }
.badge.insufficient { background: rgba(93,107,124,0.2); color: var(--text-2); }
.badge.pass { background: rgba(79,174,132,0.15); color: var(--pos); }
.badge.limitations { background: rgba(217,168,92,0.15); color: var(--warn); }
.badge.uncalibrated { background: rgba(91,155,217,0.15); color: var(--accent-2); }
.badge.insufficientdata, .badge.rejected { background: rgba(217,105,92,0.15); color: var(--neg); }

.note { font-size: 11.5px; color: var(--text-3); border-left: 2px solid var(--accent); padding: 10px 14px;
        background: var(--surface-2); margin-top: 4px; }
.footer { color: var(--text-3); font-size: 11px; padding: 24px 32px; border-top: 1px solid var(--border); }
"""

NAV_ITEMS = [
    ("index.html", "Overview"),
    ("dashboard_02_market_locality.html", "Market & Locality"),
    ("dashboard_03_property_investment.html", "Property & Investment"),
    ("dashboard_04_financial_risk.html", "Financial & Risk"),
    ("dashboard_05_geo.html", "Geo Intelligence"),
    ("dashboard_06_decision.html", "Decision Intelligence"),
    ("dashboard_07_data_quality.html", "Data Quality"),
]


def nav_html(active_file):
    links = []
    for href, label in NAV_ITEMS:
        cls = "active" if href == active_file else ""
        links.append(f'<a class="{cls}" href="{href}">{label}</a>')
    return "\n      ".join(links)


def shell(active_file, title, subtitle, body_html):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title} — Real Estate AI Decision Intelligence Platform</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.4/chart.umd.min.js"></script>
<style>{BASE_CSS}</style>
</head>
<body>
<div class="topbar">
  <div>
    <h1>{title}</h1>
    <div class="subtitle">{subtitle}</div>
  </div>
  <nav>
      {nav_html(active_file)}
  </nav>
</div>
<div class="page">
{body_html}
</div>
<div class="footer">
  Phase 10A mockup — Power BI data marts in <code>data_marts/*.csv</code>. Rendered from governed Phase 6/7/8/9 outputs, no numbers recomputed here. See docs/limitations.md.
</div>
</body>
</html>"""
