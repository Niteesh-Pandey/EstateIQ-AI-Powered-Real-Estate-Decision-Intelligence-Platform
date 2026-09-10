# PHASE 10A — Decision Experience & Power BI (Data Marts + Dashboards 1-7)
## Real Estate AI Decision Intelligence Platform

Phase 10 was split into 10A (this phase: Power BI architecture + all 7 dashboards) and 10B (the AI Explanation Layer, §10.10 — next). Matches the established convention: governed-output-only data layer, documented architecture, automated build scripts.

## What was built

**Data marts** (`data_marts/*.csv`, 12 files) — built by `src/marts/build_marts.py`, reading exclusively from Phase 6/7/8/9's already-tested CSV outputs (no financial/risk/geo/decision math recomputed here). `src/marts/test_phase10a.py` — 9 automated tests, all passing (added during a post-delivery audit that also caught an inherited Phase 6 ROI bug in the source CSVs -- see `docs/phase10a_report.md` Section 5B).

**7 dashboards** (`dashboards/*.html`) — self-contained, data-accurate HTML pages:

| File | Dashboard |
|---|---|
| `index.html` | 1 — Executive Overview |
| `dashboard_02_market_locality.html` | 2 — Market & Locality Intelligence |
| `dashboard_03_property_investment.html` | 3 — Property & Investment Analysis |
| `dashboard_04_financial_risk.html` | 4 — Financial & Risk Intelligence |
| `dashboard_05_geo.html` | 5 — Geo Intelligence |
| `dashboard_06_decision.html` | 6 — Decision Intelligence |
| `dashboard_07_data_quality.html` | 7 — Data Quality & Monitoring |

Open any of these directly in a browser — they're fully self-contained (Chart.js + Google Fonts load from CDN, everything else is embedded).

`docs/power_bi_architecture.md` — star-schema data model, DAX measures library, and a literal build guide for turning these marts into a real Power BI `.pbix`.

Full detail: **`docs/phase10a_report.md`**, **`docs/limitations.md`**.

## Why HTML mockups instead of a `.pbix` file

This build environment has no Power BI Desktop and cannot produce a `.pbix` binary. Instead, this phase delivers the two things that actually determine whether a real Power BI build will be correct: clean governed data marts, and data-accurate previews of every dashboard, plus a complete build guide. Stated plainly in the report rather than glossed over.

## A real bug found and fixed

Visual QA on Dashboard 3 caught property_id=1 showing "nan" for its locality — a join-scope bug (locality name was sourced only from properties *with* full financial data, and property 1 was deliberately included without that data to demonstrate the INSUFFICIENT decision path). Fixed by sourcing locality name independently for every property. Details in `docs/phase10a_report.md` Section 5.

## How to run

```bash
cd phase10a
pip install -r requirements-phase10a.txt --break-system-packages

python3 src/marts/build_marts.py           # rebuilds data_marts/*.csv
python3 src/dashboards/dashboard_01_executive.py
python3 src/dashboards/dashboard_02_market_locality.py
python3 src/dashboards/dashboard_03_property_investment.py
python3 src/dashboards/dashboard_04_financial_risk.py
python3 src/dashboards/dashboard_05_geo.py
python3 src/dashboards/dashboard_06_decision.py
python3 src/dashboards/dashboard_07_data_quality.py
# -> writes/refreshes dashboards/*.html
```

Then open any file in `dashboards/` in a browser.
