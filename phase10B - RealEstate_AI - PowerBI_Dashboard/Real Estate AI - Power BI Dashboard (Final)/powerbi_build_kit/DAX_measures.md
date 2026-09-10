# DAX Measures — Copy-Paste Ready
Real Estate AI Decision Intelligence Platform — Power BI Build Kit

How to use: In Power BI Desktop, right-click the relevant table in the
Fields pane → "New measure" → paste the DAX below → Enter.

═══════════════════════════════════════════════════════════════════
PAGE 1 — EXECUTIVE OVERVIEW
(table: mart_01_portfolio_kpis)
═══════════════════════════════════════════════════════════════════

-- % of properties fully evaluated (data coverage KPI)
Pct Fully Evaluated =
DIVIDE(
    SUM(mart_01_portfolio_kpis[properties_with_full_decision_evaluation]),
    SUM(mart_01_portfolio_kpis[total_properties_in_platform])
) * 100

-- % INVEST rate among evaluated properties
Pct Invest Rate =
DIVIDE(
    SUM(mart_01_portfolio_kpis[decision_invest_count]),
    SUM(mart_01_portfolio_kpis[properties_with_full_decision_evaluation])
) * 100

Note: for the decision distribution donut chart, use the separate
reshaped file `mart_01b_decision_distribution.csv` (decision, count, pct
columns) instead of writing DAX to unpivot the wide mart_01 columns --
it's already in the right shape to drag straight into a donut/pie chart
(Legend = decision, Values = count).

═══════════════════════════════════════════════════════════════════
PAGE 2 — MARKET & LOCALITY INTELLIGENCE
(table: mart_02_market_locality)
═══════════════════════════════════════════════════════════════════

-- Demand/Supply ratio (not precomputed in the mart -- derive here)
Demand Supply Ratio =
DIVIDE(
    SUM(mart_02_market_locality[latest_demand_index]),
    SUM(mart_02_market_locality[latest_supply_index])
)

-- Conditional formatting measure: growth direction color
-- (bind this to Conditional Formatting > Font Color on yoy_price_growth_pct)
Growth Color =
IF(
    SELECTEDVALUE(mart_02_market_locality[yoy_price_growth_pct]) >= 0,
    "#4FAE84",   -- pos green
    "#D9695C"    -- neg red
)

═══════════════════════════════════════════════════════════════════
PAGE 3 — PROPERTY & INVESTMENT ANALYSIS
(table: mart_03_property_investment)
═══════════════════════════════════════════════════════════════════

-- Valuation gap direction label (underpriced / overpriced / fair)
Valuation Gap Label =
VAR gap = SELECTEDVALUE(mart_03_property_investment[valuation_gap_pct])
RETURN
    SWITCH(
        TRUE(),
        gap > 5, "Underpriced (model > asking)",
        gap < -5, "Overpriced (model < asking)",
        "Fairly priced"
    )

-- Conditional formatting color for the valuation gap bar chart
Valuation Gap Color =
VAR gap = SELECTEDVALUE(mart_03_property_investment[valuation_gap_pct])
RETURN IF(gap >= 0, "#4FAE84", "#D9695C")

-- Count of properties by decision (for the slicer summary card)
Property Count = COUNTROWS(mart_03_property_investment)

═══════════════════════════════════════════════════════════════════
PAGE 4 — FINANCIAL & RISK INTELLIGENCE
(tables: mart_04_financial_risk, mart_04c_scenarios_extended4)
═══════════════════════════════════════════════════════════════════

-- IRR as a whole percentage for card display (source is a decimal, e.g. 0.1785)
IRR Pct = AVERAGE(mart_04_financial_risk[irr]) * 100

-- ROI as a percentage (source is a ratio, e.g. 1.2377 = 123.77%)
ROI Pct = AVERAGE(mart_04_financial_risk[roi_total_holding_period]) * 100

-- Probability of negative NPV as a whole percentage
Prob Negative NPV Pct = AVERAGE(mart_04_financial_risk[probability_negative_npv]) * 100

-- Average DSCR (some rows may be blank/N-A if no financing data -- AVERAGE ignores blanks automatically)
Avg DSCR = AVERAGE(mart_04_financial_risk[dscr])

-- Scenario spread label for the tornado/waterfall chart ordering
-- (add a calculated column, not a measure, on mart_04c_scenarios_extended4)
Scenario Order =
SWITCH(
    mart_04c_scenarios_extended4[scenario],
    "Severe Downside", 1,
    "Downside", 2,
    "Base", 3,
    "Upside", 4,
    5
)
-- After adding this column: right-click "scenario" column > Sort by Column > Scenario Order
-- so the X-axis reads Severe Downside -> Downside -> Base -> Upside left to right.

═══════════════════════════════════════════════════════════════════
PAGE 5 — GEO INTELLIGENCE
(table: mart_05_geo)
═══════════════════════════════════════════════════════════════════

-- Count of localities with INSUFFICIENT DATA flood risk (for an honesty callout card)
Localities Missing Flood Data =
CALCULATE(
    COUNTROWS(mart_05_geo),
    mart_05_geo[flood_risk_status] = "INSUFFICIENT DATA"
)

-- % of portfolio with missing flood/environmental data
Pct Missing Flood Data =
DIVIDE([Localities Missing Flood Data], COUNTROWS(mart_05_geo)) * 100

═══════════════════════════════════════════════════════════════════
PAGE 6 — DECISION INTELLIGENCE
(tables: mart_06_decision_summary, mart_06b_decision_components,
 mart_06c_decision_gates, mart_06d_decision_reasons)
═══════════════════════════════════════════════════════════════════

-- Decision badge color (for conditional formatting on the decision column/matrix)
Decision Color =
SWITCH(
    SELECTEDVALUE(mart_06_decision_summary[decision]),
    "INVEST", "#4FAE84",
    "HOLD", "#D9A85C",
    "AVOID", "#D9695C",
    "INSUFFICIENT", "#5D6B7C",
    "#5D6B7C"
)

-- Gate pass rate (for the critical-gates page, mart_06c)
Gate Pass Rate =
DIVIDE(
    CALCULATE(COUNTROWS(mart_06c_decision_gates), mart_06c_decision_gates[passed] = TRUE),
    COUNTROWS(mart_06c_decision_gates)
) * 100

-- Average component score per component (for the stacked/radar chart, mart_06b)
Avg Component Score = AVERAGE(mart_06b_decision_components[score])

═══════════════════════════════════════════════════════════════════
PAGE 7 — DATA QUALITY & MONITORING
(table: mart_07_data_quality)
═══════════════════════════════════════════════════════════════════

-- Count of REJECTED models (this is the number worth highlighting in
-- an interview -- it proves governance, not just that models exist)
Rejected Model Count =
CALCULATE(
    COUNTROWS(mart_07_data_quality),
    mart_07_data_quality[status] = "REJECTED"
)

-- Status color for the data-quality status column
Status Color =
SWITCH(
    SELECTEDVALUE(mart_07_data_quality[status]),
    "PASS", "#4FAE84",
    "PASS WITH LIMITATIONS", "#D9A85C",
    "CONDITIONAL", "#D9A85C",
    "REJECTED", "#D9695C",
    "UNCALIBRATED", "#5B9BD9",
    "INSUFFICIENT DATA", "#5D6B7C",
    "#5D6B7C"
)
