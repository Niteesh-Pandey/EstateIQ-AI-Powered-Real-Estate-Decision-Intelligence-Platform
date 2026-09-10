# Real Estate AI Decision Intelligence Platform — Power BI Dashboard (Final Package)

This package is the final, consolidated Power BI deliverable for the platform's
10-phase architecture (Master A–Z Development Prompt). It merges two things
into one:

1. **The generated data layer and reference code** (`phase10a_source/`) —
   the 12 Power BI data marts, the Python code that built them, the source
   CSVs each mart was derived from, automated tests, and full documentation.
2. **The actual, hand-built Power BI report** (`Real_estate_dashboard.pbix`)
   — built directly in Power BI Desktop from those 12 marts, across 7 pages,
   plus screenshots of the finished result.

---

## What's in this package

```
Real_estate_dashboard.pbix        <- Open this in Power BI Desktop
dashboard_screenshots/            <- 7 PNG screenshots of the finished report
phase10a_source/                  <- Full backend: code, marts, tests, docs
powerbi_build_kit/                <- Build guide, DAX measures, color theme
```

### `Real_estate_dashboard.pbix`
The actual Power BI file. Open it directly in Power BI Desktop — no setup
required, all data is embedded. Contains 7 report pages (see screenshots
below for what each one looks like).

### `dashboard_screenshots/`
| File | Page |
|---|---|
| `01_executive_overview.png` | Portfolio KPIs, decision distribution donut, invest rate |
| `02_market_locality_intelligence.png` | Top-15 price growth chart, demand-vs-supply scatter, city filter |
| `03_property_investment.png` | Property table, valuation-gap chart, decision filter |
| `04_financial_risk.png` | IRR/NPV/DSCR table, Monte Carlo scenario chart, VaR/CVaR cards, UNCALIBRATED disclaimer |
| `05_geo_intelligence.png` | Locality map, accessibility/transit/commercial scores, flood-data-gap card |
| `06_decision_intelligence.png` | Component-score breakdown, gate pass-rate, per-property decision table, reasons |
| `07_data_quality_monitoring.png` | Full governance status table, rejected-model count, status distribution |

### `phase10a_source/`
The complete backend that produced the 12 CSV data marts the `.pbix` file
was built from — `src/marts/build_marts.py`, the source CSVs under
`sources/phase6` through `sources/phase9`, the `data_marts/*.csv` outputs
themselves, the automated test suite (`src/marts/test_phase10a.py`), and
full phase documentation (`docs/phase10a_report.md`, `docs/limitations.md`).

### `powerbi_build_kit/`
Reference material used to build the report: a step-by-step build guide
(`POWER_BI_BUILD_GUIDE.md`/`.pdf`), ready-to-paste DAX measures
(`DAX_measures.md`), and the custom Power BI color theme
(`power_bi_theme.json`) matching the platform's dark gold/green/red palette.

---

## Independent recheck performed before this package was assembled

Since this package combines two separately-delivered pieces (the generated
marts and the hand-built `.pbix`), the following was re-verified end to end:

1. **ROI calculation fix confirmed present.** `phase10a_source/src/finance/engine.py`
   was checked and confirmed to contain the corrected `roi_total_holding_period`
   formula (net return, not gross cash multiple) — the fix found during a
   prior audit of Phase 6 and traced through Phases 7, 9, and this phase.
   Verified directly: property 2731's Base-case ROI in `mart_04_financial_risk.csv`
   is **123.77%**, consistent with its 17.85% IRR compounded over a 5-year
   hold (not the pre-fix 223.77%).

2. **Automated test suite re-run: 9/9 passing.**
   `phase10a_source/src/marts/test_phase10a.py` was executed fresh inside
   this package — covering the ROI regression check, cross-scenario
   IRR/ROI monotonicity, the property-1 NaN-locality-name regression check,
   portfolio-KPI-vs-decision-source consistency, and structural checks that
   no financial/risk formula is recomputed in the mart-building code.

3. **Data-mart consistency confirmed byte-for-byte.** Every one of the 12
   CSV files under `phase10a_source/data_marts/` was diffed against the
   copy that was actually used to build `Real_estate_dashboard.pbix`
   (originally supplied separately as the "build kit" data). All 12 files
   are identical — confirming the `.pbix` was built from the correct,
   already-fixed data, not a stale copy.

4. **All 7 dashboard screenshots reviewed.** Each of the issues found and
   fixed during the interactive build process is confirmed resolved in the
   final screenshots: Page 3's valuation-gap chart uses a categorical
   (not continuous) axis; Page 4's probability/VaR/CVaR cards use Average
   (not Sum) aggregation and carry the UNCALIBRATED disclaimer text box;
   Page 5's flood-risk-data-gap card shows a real percentage (100%) with
   an explanatory note about partial transit/commercial score coverage;
   Page 6's decision table shows one row per property with genuinely
   distinct scores (not grouped/summed by decision category); Page 7's
   column headers are correctly labeled and the Rejected Model Count card
   correctly reads 2 (not the row-count of 1).

No further issues were found. This package is internally consistent and
ready to present.

---

## Key facts for a resume, portfolio page, or interview

- **26 properties fully evaluated** end-to-end through a 9-phase decision
  pipeline (data → SQL analytics → EDA → 7 ML models → evidence/RAG →
  financial engine → Monte Carlo risk → geo scoring → multi-agent decision
  policy), surfaced here as a 7-page interactive Power BI report.
- **2 of 7 ML models were rejected** after independent validation showed
  near-random predictive power (R² ≈ 0 for days-on-market, ROC-AUC ≈ 0.52
  for sale probability) — shown transparently on the Data Quality page
  rather than hidden.
- **Every Monte Carlo/VaR/CVaR figure is explicitly labeled UNCALIBRATED**
  — a documented judgement call, not fitted to real historical outcomes.
  This is stated directly on the Financial & Risk page, not buried in a
  footnote.
- **Data gaps are shown honestly, not imputed.** The Geo Intelligence page
  states plainly that flood-risk data is unavailable for 100% of
  localities, and that transit/commercial accessibility scores only exist
  where the underlying infrastructure records do.
- **Every decision is explainable.** Page 6 lets you click any property
  and see exactly which of 5 weighted components (market, prediction,
  financial, risk, geo) drove its score, which governance gates it passed,
  and the specific stated reasons behind the INVEST/HOLD/AVOID/INSUFFICIENT
  call.
- **One real, systematic bug (the ROI calculation) was found during
  independent audit and fixed across every phase it had propagated into**
  — a concrete example of QA discipline applied to a multi-stage data
  pipeline, not just a one-off model built and shipped.

---

## How to open

1. Extract this package.
2. Double-click `Real_estate_dashboard.pbix` to open it directly in Power
   BI Desktop — all data is embedded, no data source reconnection needed.
3. To see the source data pipeline or re-run the tests, see
   `phase10a_source/README_PHASE10A.md`.
