# POWER BI ARCHITECTURE
## Phase 10A — Section 10.2

## 1. Why HTML mockups, not a `.pbix` file

This build environment has no Power BI Desktop installed and no way to produce a genuine `.pbix` binary. Claiming to deliver one would be dishonest. Instead, this phase delivers the two things that actually determine whether a real Power BI build will be correct:

1. **The data marts** (`data_marts/*.csv`) — exactly the flat, governed tables Power BI's data model should import. These are what a Power BI developer connects to.
2. **Interactive HTML dashboard mockups** (`dashboards/*.html`) — pixel-accurate previews of what each of the 7 dashboards shows, built from the *same* mart data, so stakeholders can review the actual numbers and layout before anyone opens Power BI Desktop.

Section 5 below is a literal build guide for turning these marts into a real `.pbix`.

## 2. Governed-output rule, enforced

> "Power BI should consume governed outputs from SQL, analytics, models, finance, risk, geo, decision engine. Do not duplicate complex backend calculations unnecessarily in DAX." — §10.2

Every mart in `data_marts/` is built by `src/marts/build_marts.py`, which reads **only** from:
- Phase 6's `docs/financial_results_csv/*.csv` (NOI, IRR, NPV, cap rate, DSCR — never recomputed)
- Phase 7's `docs/risk_results_csv/*.csv` (VaR, CVaR, probabilities, decision stability — never recomputed)
- Phase 8's `docs/geo_results_csv/*.csv` (location score, accessibility, geo risk — never recomputed)
- Phase 9's `docs/decision_results_csv/*.csv` (decision, score, confidence, reasons — never recomputed)
- Phase 4's trained model artifacts, used only for a fresh valuation/rent prediction on the demo batch's specific properties (the model itself is Phase 4's, unchanged)
- `core.market_monthly` directly, for locality-level demand/supply/growth — because Phase 2 produced SQL views but no CSV export; this one exception reuses Phase 8's own tested `_market_intelligence()` function rather than writing new aggregation logic

No file in `src/marts/` contains an IRR formula, a Monte Carlo loop, a location-score weight, or a decision-policy threshold. If you open `build_marts.py` looking for "the math," you won't find it — that's the point.

## 3. Data model — star schema

```
                    ┌─────────────────────┐
                    │  dim_locality        │
                    │  (mart_02, mart_05)  │
                    └──────────┬───────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
┌───────▼────────┐   ┌─────────▼─────────┐   ┌────────▼─────────┐
│ fact_property    │   │ fact_market        │   │ fact_geo          │
│ (mart_03)        │   │ (mart_02)          │   │ (mart_05)         │
└───────┬──────────┘   └────────────────────┘   └───────────────────┘
        │
┌───────▼──────────┐   ┌────────────────────┐
│ fact_financial_risk│   │ fact_decision       │
│ (mart_04, 04b, 04c)│   │ (mart_06, 06b-d)    │
└─────────────────────┘   └────────────────────┘
```

`property_id` is the grain for `fact_property`, `fact_financial_risk`, and `fact_decision`. `locality_id` is the grain for `fact_market` and `fact_geo`. `mart_01_portfolio_kpis.csv` is a single-row table for headline KPI cards (Power BI: no relationship needed, use it as an isolated table for card visuals).

## 4. DAX measures library (reference — not executed in this environment)

These are written as documentation for the Power BI developer who imports the marts; they are **not** run anywhere in this deliverable, since no `.pbix` exists here.

```dax
Mean Decision Score = AVERAGE(fact_decision[decision_score])

Mean Decision Confidence = AVERAGE(fact_decision[decision_confidence])

Invest Count = CALCULATE(COUNTROWS(fact_decision), fact_decision[decision] = "INVEST")

Pct Portfolio Full Coverage =
    DIVIDE(
        CALCULATE(COUNTROWS(fact_property), fact_financial_risk[base_validation_status] = "PASS"),
        COUNTROWS(fact_property)
    )

Median Cap Rate = MEDIAN(fact_financial_risk[cap_rate])

Mean Prob Negative NPV = AVERAGE(fact_financial_risk[probability_negative_npv])
-- NOTE: this measure name should carry a visible "(simulated, UNCALIBRATED)"
-- suffix or tooltip in any dashboard that surfaces it -- see Section 6.

Top Locality by Demand =
    TOPN(1, fact_market, fact_market[latest_demand_index], DESC)
```

## 5. Build guide — from these marts to a real `.pbix`

1. Open Power BI Desktop → Get Data → Text/CSV → import all files in `data_marts/`.
2. Set relationships per the star schema in Section 3 (Model view → drag `locality_id` / `property_id` between tables; use single-direction filters from dimension → fact).
3. Build the 7 report pages using this deliverable's `dashboards/*.html` as the visual/layout reference — same KPI cards, same chart types (bar, scatter, doughnut), same table columns.
4. Paste the DAX measures from Section 4 into each fact table.
5. Set data source credentials to the live PostgreSQL instance (see Section 6) once available; until then, the CSV marts are the source.
6. Publish to the Power BI Service; set scheduled refresh per Section 7.

## 6. Governance carried into the BI layer

Every status field that reached this phase (`PASS` / `PASS WITH LIMITATIONS` / `CONDITIONAL` / `REJECTED` / `UNCALIBRATED` / `INSUFFICIENT DATA`) is preserved as its own column in the marts — never collapsed into a single "OK/Not OK" flag. Dashboard 4 and Dashboard 6 both visually flag every UNCALIBRATED figure. A Power BI developer building the real report must not drop these status columns for a "cleaner" look — they are the platform's honesty mechanism, and Section 24's "Production-Oriented Prototype" positioning depends on them staying visible.

## 7. Refresh strategy (documented target, not implemented here)

| Data | Suggested refresh |
|---|---|
| `mart_01`, `mart_06*` (decision) | On-demand, whenever Phase 9's pipeline is re-run for a property/batch |
| `mart_02` (market/locality) | Monthly, matching `core.market_monthly`'s own monthly grain |
| `mart_03` (property/investment) | Weekly, or whenever new properties enter the portfolio |
| `mart_04*` (financial/risk) | Weekly, or when financial assumptions change |
| `mart_05` (geo) | Quarterly — locality/infrastructure data changes slowly |
| `mart_07` (data quality) | Same cadence as the underlying phase's own test suite runs |

No refresh automation exists in this deliverable — this table is a documented target for whoever owns the live Power BI Service deployment.
