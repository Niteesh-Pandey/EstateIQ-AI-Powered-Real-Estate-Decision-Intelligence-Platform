# Power BI Build Guide
## Real Estate AI Decision Intelligence Platform — Phase 10A

This guide gets you from the 12 data-mart CSVs to a finished, presentable
`.pbix` file. Follow it top to bottom. Everything referenced here is in
`phase10a/data_marts/` plus 3 extra files in this kit
(`mart_01b_decision_distribution.csv`, `power_bi_theme.json`,
`DAX_measures.md`).

Estimated time: 3-4 hours for all 7 pages.

---

## STEP 0 — Files you need in one folder before starting

Copy these into a single folder (e.g. `powerbi_build/`):
- All 12 files from `phase10a/data_marts/*.csv`
- `mart_01b_decision_distribution.csv` (from this kit)
- `power_bi_theme.json` (from this kit)
- Keep `DAX_measures.md` open in a text editor for copy-pasting as you go

---

## STEP 1 — Import all 13 CSVs

1. Open Power BI Desktop → **Home → Get Data → Text/CSV**
2. Import each file one at a time (or use **Get Data → Folder** and point
   at your `powerbi_build/` folder to bring in all 13 at once)
3. For each, click **Transform Data** and check:
   - `property_id` / `locality_id` columns are typed as **Whole Number**
   - Percentage columns (`irr`, `roi_total_holding_period`,
     `probability_negative_npv`, `yoy_price_growth_pct`, etc.) are typed
     as **Decimal Number** — you will format them as % at the visual level,
     don't multiply by 100 in Power Query
   - `decision`, `status`, `scenario`, `source`, `topic` columns are typed
     as **Text**
4. Click **Close & Apply**

---

## STEP 2 — Apply the theme

**View → Themes → Browse for themes** → select `power_bi_theme.json`.
This gives you the same dark palette as the HTML mockups (gold accent
`#D9A85C`, green `#4FAE84` for positive, red `#D9695C` for negative).

---

## STEP 3 — Build relationships (Model view)

Click **Model** on the left rail. Drag to create these relationships:

| From | To | Key | Cardinality |
|---|---|---|---|
| `mart_03_property_investment` | `mart_04_financial_risk` | `property_id` | 1:1 |
| `mart_03_property_investment` | `mart_06_decision_summary` | `property_id` | 1:1 |
| `mart_03_property_investment` | `mart_04b_scenarios_base3` | `property_id` | 1:many |
| `mart_03_property_investment` | `mart_04c_scenarios_extended4` | `property_id` | 1:many |
| `mart_06_decision_summary` | `mart_06b_decision_components` | `property_id` | 1:many |
| `mart_06_decision_summary` | `mart_06c_decision_gates` | `property_id` | 1:many |
| `mart_06_decision_summary` | `mart_06d_decision_reasons` | `property_id` | 1:many |
| `mart_02_market_locality` | `mart_05_geo` | `locality_id` | 1:1 |

**Leave unconnected** (by design, not an oversight):
- `mart_01_portfolio_kpis` — single summary row, used standalone on Page 1
- `mart_07_data_quality` — standalone qualitative table, used on Page 7
- Property-level marts (03/04/06...) have no `locality_id` column (only
  `locality_name` text) — so they are NOT related to `mart_02`/`mart_05`
  in this build. If you want cross-filtering between the property pages
  and the locality pages later, relate on `locality_name` (text
  relationship) — but note two different cities could theoretically share
  a locality name, so treat this as an optional advanced step, not a
  default.

---

## STEP 4 — Add the DAX measures

Open `DAX_measures.md` and paste each measure into its listed table
(right-click the table in the **Fields** pane → **New measure**). Do this
now so they're available while building visuals below.

---

## STEP 5 — Build the 7 report pages

Add 7 pages (right-click the page tab → rename each). For every page,
first add a **Text box** at the top with the page title, matching the
HTML mockup headers.

### Page 1 — Executive Overview
*Source: `mart_01_portfolio_kpis`, `mart_01b_decision_distribution`*

| Visual | Type | Fields |
|---|---|---|
| Top KPI row (4 cards) | Card | `total_properties_in_platform`, `total_localities`, `mean_decision_score`, `mean_decision_confidence` |
| Decision split | Donut chart | Legend = `decision`, Values = `count` (from `mart_01b_decision_distribution`) |
| Coverage KPI | Card + gauge | `[Pct Fully Evaluated]` measure |
| Invest rate | Card | `[Pct Invest Rate]` measure |

Conditional formatting: on the donut chart, set data colors manually —
INVEST=`#4FAE84`, HOLD=`#D9A85C`, AVOID=`#D9695C`, INSUFFICIENT=`#5D6B7C`
(right-click the visual → Format → Colors → click each legend swatch).

### Page 2 — Market & Locality Intelligence
*Source: `mart_02_market_locality`*

| Visual | Type | Fields |
|---|---|---|
| Price growth by locality | Clustered bar chart | Axis = `locality_name`, Values = `yoy_price_growth_pct`, sort descending |
| Demand vs supply | Scatter chart | X = `latest_demand_index`, Y = `latest_supply_index`, Size = `location_score`, Details = `locality_name` |
| Top localities table | Table | `locality_name`, `city_name`, `latest_price_sqft`, `growth_rank`, `demand_supply_rank` (sort by `growth_rank` ascending) |
| Slicer | Slicer | `city_name` |

Apply `[Growth Color]` measure to the bar chart via Conditional
Formatting → Font color → Format by: Field value → `Growth Color`.

### Page 3 — Property & Investment Analysis
*Source: `mart_03_property_investment`*

| Visual | Type | Fields |
|---|---|---|
| Property table | Table/Matrix | `property_id`, `property_type`, `area_sqft`, `asking_price`, `predicted_valuation`, `valuation_gap_pct`, `decision` |
| Valuation gap chart | Bar chart | Axis = `property_id`, Values = `valuation_gap_pct` |
| Slicer | Slicer | `decision` |
| Property count | Card | `[Property Count]` measure |

Apply `[Valuation Gap Color]` to the bar chart (same conditional-formatting
method as Page 2).

### Page 4 — Financial & Risk Intelligence
*Source: `mart_04_financial_risk`, `mart_04c_scenarios_extended4`*

| Visual | Type | Fields |
|---|---|---|
| Financial summary table | Table | `property_id`, `irr`, `npv`, `cap_rate`, `dscr`, `roi_total_holding_period` |
| Scenario spread | Line/column chart | Axis = `scenario` (sorted by the `Scenario Order` column you added), Values = `irr`, Legend = `property_id` |
| Risk KPIs row | Cards | `[Prob Negative NPV Pct]`, `probability_meets_target_irr`, `var_95_npv`, `cvar_95_npv` |
| Cap rate vs cash-on-cash | Scatter | X = `cap_rate`, Y = `cash_on_cash_return`, Details = `property_id` |

**Add a text box** on this page: *"UNCALIBRATED — every probability/VaR/
CVaR figure comes from Phase 7's Monte Carlo engine, whose distribution
bounds are documented judgement calls, not fitted to real historical
outcomes."* This single sentence is what makes this page credible in an
interview — don't skip it.

### Page 5 — Geo Intelligence
*Source: `mart_05_geo`*

| Visual | Type | Fields |
|---|---|---|
| Locality map | Map (or ArcGIS Map for more control) | Location: `latitude`/`longitude`, Size = `location_score`, Tooltip = `locality_name`, `accessibility_score` |
| Score comparison | Clustered bar | Axis = `locality_name`, Values = `accessibility_score`, `transit_score`, `commercial_score` |
| Data-gap callout | Card | `[Pct Missing Flood Data]` measure, label it "% localities: flood risk data unavailable" |

Do not hide or soften the flood-data-gap card — it's a governance
strength, not a weakness, when framed correctly (see the report's own
Section on this).

### Page 6 — Decision Intelligence (the most important page)
*Source: `mart_06_decision_summary`, `mart_06b_decision_components`,
`mart_06c_decision_gates`, `mart_06d_decision_reasons`*

| Visual | Type | Fields |
|---|---|---|
| Decision matrix | Table/Matrix | `property_id`, `decision`, `decision_score`, `decision_confidence` |
| Component breakdown | Stacked bar chart | Axis = `property_id`, Values = `score`, Legend = `component` |
| Gate pass/fail | Table with icons | `property_id`, `gate`, `passed` (conditional icon: ✅/❌) |
| Reasons & risks | Table | `property_id`, `type`, `text` (filter by selected property via a slicer or click-to-filter from the matrix) |
| Gate pass rate | Card | `[Gate Pass Rate]` measure |

Apply `[Decision Color]` to the decision matrix (Conditional Formatting →
Background color → Field value → `Decision Color`).

**Make this page interactive**: set the decision matrix as the filter
source — click a property row and have the component/gates/reasons
visuals cross-filter automatically (Power BI does this by default via the
`property_id` relationship). This is the single best "wow" moment for a
live demo — click a property, watch its whole reasoning update.

### Page 7 — Data Quality & Monitoring
*Source: `mart_07_data_quality`*

| Visual | Type | Fields |
|---|---|---|
| Status table | Table | `phase`, `metric`, `value`, `status` |
| Rejected models callout | Card | `[Rejected Model Count]` measure |
| Status distribution | Bar chart | Axis = `status`, Values = count of rows |

Apply `[Status Color]` to the status table's `status` column
(Conditional Formatting → Font color → Field value).

**Talking point for this page in an interview**: point at the REJECTED
row and explain *why* (e.g. days-on-market model showed R²≈0, sale
probability showed ROC-AUC≈0.52 — both confirmed near-random and
withheld from production use). This is what separates this project from
most portfolio ML projects.

---

## STEP 6 — Add page navigation

**Insert → Buttons → Blank button** on each page, styled as a small nav
bar (matches the HTML mockup's top-right nav). Set each button's action
to **Page navigation** → target page. Copy one button, paste 7 times,
retarget each.

---

## STEP 7 — Save and rehearse

1. **File → Save As** → `RealEstateAI_DecisionIntelligence.pbix`
2. Before presenting: click through all 7 pages once, click a property on
   Page 6 to confirm cross-filtering works, and re-read the Page 4
   UNCALIBRATED text box out loud once — it should feel natural to say in
   an interview, not like a disclaimer you're hiding.

---

## Common Import Issues

- **Percentages showing as 1785% instead of 17.85%**: you formatted the
  visual as a percentage AND the source is already ×100. Check whether
  the mart column is a raw decimal (0.1785) or already a percent number
  — `irr`, `roi_total_holding_period`, `probability_*` are raw decimals
  in every mart; format as % at the visual level, don't transform the
  data.
- **Relationships showing as dotted/inactive lines**: Power BI only
  allows one active relationship per table pair by default — if you see
  a dotted line, right-click it → Properties → make it active, or use
  `USERELATIONSHIP()` in a measure if you deliberately need both.
- **Map visual shows nothing**: confirm `latitude`/`longitude` are typed
  as Decimal Number, not Text, in Power Query.
