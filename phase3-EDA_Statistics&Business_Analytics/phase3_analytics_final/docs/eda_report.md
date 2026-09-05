# Real Estate Platform — EDA & Statistical Analytics Report

*Generated 2026-09-02 05:09 against live PostgreSQL (real_estate_db, PostgreSQL 16.15 (Ubuntu 16.15). Reproducible via `python3 src/analytics/generate_eda_report.py`.*

## 1. Business Objective

Understand the statistical structure of the real estate dataset — price drivers, market segmentation, time trends, and data-quality issues — to (a) validate existing ML model design choices and (b) surface findings that inform Phase 3+ model/decision engine work. This is descriptive/inferential analytics, not a new ML model.

## 2. Dataset Overview

- **Database**: `real_estate_db` (PostgreSQL, live)
- **properties row count** (live check): 8000
- **Data dictionary**: 127 columns across 15 tables — see `src/analytics/data_dictionary.py`

## 3. Data Quality

**Referential integrity** (all FK checks against live PostgreSQL):

- `localities.city_id` → `cities`: **0 orphans**
- `projects.developer_id` → `developers`: **0 orphans**
- `projects.locality_id` → `localities`: **0 orphans**
- `properties.project_id` → `projects`: **0 orphans**
- `transactions.property_id` → `properties`: **0 orphans**
- `rentals.property_id` → `properties`: **0 orphans**

**Key numeric field null rates:**

| Table.Column | N | Null % | Mean | Median | Std |
|---|---|---|---|---|---|
| properties.asking_price | 8000 | 0.0% | 12,620,282.6 | 12,222,500.0 | 4,584,262.4 |
| properties.monthly_rent | 8000 | 0.0% | 34,397.4 | 32,800.0 | 13,400.2 |
| properties.area_sqft | 8000 | 0.0% | 1,175.4 | 1,158.0 | 358.1 |
| properties.bedrooms | 8000 | 0.0% | 2.6 | 3.0 | 1.1 |
| transactions.transaction_price | 20000 | 0.0% | 31,100,878.8 | 15,609,500.0 | 115,096,197.2 |
| transactions.price_per_sqft | 20000 | 0.0% | 26,429.2 | 13,667.5 | 93,711.2 |

## 4. Descriptive Statistics

| Metric | N | Mean | Median | Std | P95 | CV |
|---|---|---|---|---|---|---|
| Property asking price (₹) | 8000 | 12,620,282.6 | 12,222,500.0 | 4,584,262.4 | 20,487,000.0 | 0.36 |
| Property monthly rent (₹) | 8000 | 34,397.4 | 32,800.0 | 13,400.2 | 58,700.0 | 0.39 |
| Property area (sqft) | 8000 | 1,175.4 | 1,158.0 | 358.1 | 1,790.0 | 0.30 |
| Actual transaction price (₹) | 20000 | 31,100,878.8 | 15,609,500.0 | 115,096,197.2 | 64,460,100.0 | 3.70 |
| Transaction price per sqft (₹) | 20000 | 26,429.2 | 13,667.5 | 93,711.2 | 52,555.4 | 3.55 |
| Days on market (listing to sale/expiry) | 12000 | 75.9 | 75.0 | 42.8 | 149.0 | 0.56 |
| Locality-month demand index (0-100) | 6480 | 76.0 | 76.9 | 15.5 | 98.2 | 0.20 |
| Locality-month supply index (0-100) | 6480 | 47.3 | 46.8 | 14.9 | 72.9 | 0.31 |
| Available inventory (units) | 6480 | 77.9 | 69.0 | 52.1 | 175.0 | 0.67 |
| Units sold per locality-month | 6480 | 91.0 | 93.0 | 21.2 | 123.0 | 0.23 |
| Gross rental yield (%) | 8000 | 3.3 | 3.3 | 0.6 | 4.3 | n/a |

## 5. Distribution Analysis

| Metric | Skewness | Shape | Excess Kurtosis | Tail Behavior |
|---|---|---|---|---|
| Asking Price (₹) | 1.118 | strongly right-skewed | 4.843 | heavy-tailed (more extreme outliers than a normal distribution) |
| Property Area (sqft) | 0.203 | approximately symmetric | -0.269 | approximately normal tail weight |
| Monthly Rent (₹) | 0.721 | right-skewed (long tail toward high values) | 0.776 | approximately normal tail weight |
| Transaction Price/SqFt (₹) | 12.248 | strongly right-skewed | 171.927 | heavy-tailed (more extreme outliers than a normal distribution) |
| Days on Market | 0.291 | approximately symmetric | -0.338 | approximately normal tail weight |
| Demand Index (0-100) | -0.357 | approximately symmetric | -0.677 | approximately normal tail weight |

Charts saved to `docs/eda_charts/`: dist_asking_price.png, dist_area_sqft.png, dist_monthly_rent.png, dist_price_per_sqft.png, dist_days_on_market.png, dist_demand_index.png

## 6. Correlation Analysis

*Correlation does not imply causation — all relationships below are observed associations only.*

**Strongest property-level correlations (Pearson):**

- `area_sqft` ↔ `asking_price`: r = 0.838
- `area_sqft` ↔ `bedrooms`: r = 0.83
- `asking_price` ↔ `monthly_rent`: r = 0.824
- `area_sqft` ↔ `monthly_rent`: r = 0.773
- `bedrooms` ↔ `asking_price`: r = 0.696

**Strongest market-level correlations (Pearson):**

- `demand_index` ↔ `units_sold`: r = 0.881
- `demand_index` ↔ `available_inventory`: r = -0.762
- `demand_index` ↔ `average_days_on_market`: r = -0.69
- `units_sold` ↔ `available_inventory`: r = -0.674
- `units_sold` ↔ `average_days_on_market`: r = -0.606

Heatmaps: `correlation_property_features.png`, `correlation_market_features.png`

## 7. Segment Analysis

**By city (median price):**

| City | N | Median Price | Median ₹/sqft | Rental Yield |
|---|---|---|---|---|
| Bengaluru | 1421 | ₹13,227,000 | ₹11,470 | 3.27% |
| Pune | 1388 | ₹13,018,500 | ₹11,236 | 3.26% |
| Delhi NCR | 1214 | ₹12,522,000 | ₹10,657 | 3.32% |
| Hyderabad | 1486 | ₹11,898,500 | ₹10,178 | 3.33% |
| Mumbai | 1311 | ₹11,485,000 | ₹10,153 | 3.28% |
| Chennai | 1180 | ₹11,418,000 | ₹9,869 | 3.29% |

**Top 3 developers by sales velocity:**

- Sampath Constructions: 93.3% velocity, rating 4.9
- Bhagat Builders: 90.7% velocity, rating 4.9
- Ray Builders: 88.5% velocity, rating 4.5

## 8. Time-Series Analysis

- Observed **72 months**: 2020-01-01 to 2025-12-01
- Latest price snapshot: {"as_of_month": "2025-12-01", "value": 68724.5, "mom_growth_pct": 6.16, "yoy_growth_pct": 90.83, "rolling_12m_avg": 51141.74, "rolling_12m_volatility_pct": 0.63}
- Latest demand snapshot: {"as_of_month": "2025-12-01", "value": 83.46, "mom_growth_pct": 0.54, "yoy_growth_pct": 3.92, "rolling_12m_avg": 81.78, "rolling_12m_volatility_pct": 0.21}
- Yearly avg price/sqft: {"2020": 10818.56, "2021": 12478.52, "2022": 15069.98, "2023": 20164.11, "2024": 29606.34, "2025": 51141.74}

⚠️ **See §9 Outlier Analysis** — price growth figures are affected by data generation compounding.

## 9. Outlier Analysis

### properties.asking_price — `LEGITIMATE_EXTREME`
- IQR outliers: 121 (1.51%)
- Z-score outliers: 54 (0.68%)
- **Evidence**: 0.5% of properties.csv rows were generated with an intentional 2.5x price multiplier to simulate real market premium/luxury listings (see data/generate_data_part2.py, `out_idx` injection). This is a documented, deliberate design choice, not a bug.
- **Recommended action**: Keep as-is. Represents luxury-segment properties; useful for testing valuation model robustness to premium listings.

### transactions.transaction_price — `DATA_QUALITY_ERROR`
- IQR outliers: 1668 (8.34%)
- Z-score outliers: 191 (0.96%)
- **Evidence**: Root cause traced (see docs/eda_findings.md): transactions.price is computed as market_monthly.average_price_sqft * area_sqft. The price-growth formula in generate_data_part2.py (`psf = psf * (1 + growth)`) compounds monthly with NO ceiling or dampening. For localities with a persistently high demand/supply ratio, this causes runaway exponential growth — e.g. locality 28 goes from ₹13,592/sqft (2020-01) to ₹1,923,519/sqft (2025-12), a 141x increase in 6 years. National avg price/sqft grew 10,818 → 51,141 (YoY +90.8% in the final year) — statistically confirmed via skewness=12.2, excess kurtosis=172 on price_per_sqft (see distributions.py output).
- **Recommended action**: FIX AT SOURCE in a future data-regeneration phase: add a ceiling/mean-reversion term to the price-growth formula (e.g. cap monthly growth or add reversion toward a locality's income-implied price level). NOT fixed in this phase per Phase 2 scope (analytics/EDA only, no source-data modification). Flagged here for Phase 3+ remediation.

### listing_history.days_on_market — `NEEDS_INVESTIGATION`
- IQR outliers: 50 (0.42%)
- Z-score outliers: 26 (0.22%)
- **Evidence**: Already documented in docs/data_dictionary.md as having no feature-dependent signal (DOM ML model R²=-0.04, near-random). Outliers here are as likely to be generator noise as genuine slow-moving listings — cannot distinguish from data alone.
- **Recommended action**: Do not use DOM outliers for business decisions (Model Registry already blocks the DOM model at runtime — consistent treatment).

### derived: gross_rental_yield_pct — `LEGITIMATE_EXTREME`
- IQR outliers: 108 (1.35%)
- Z-score outliers: 38 (0.48%)
- **Evidence**: Yield is generated as np.random.normal(3.3, 0.6) independently of price — a tight, bounded distribution by construction (see generate_data_part2.py). IQR/Z-score outliers here are simply the tails of that intentional normal distribution.
- **Recommended action**: Keep as-is — expected statistical tail, not an error.

## 10. Hypothesis Testing & Effect Sizes

*Alpha = 0.05 throughout.*

### test_a_price_mumbai_vs_chennai
- **Test**: Mann-Whitney U | H0: Median asking_price is equal between Mumbai and Chennai
- **Statistic**: 788711.5, **p-value**: 0.39576, **significant**: False
- **Effect size**: {'cohens_d': 0.032, 'label': 'negligible'}
- **Interpretation**: Not statistically significant price difference between Mumbai and Chennai (p=0.3958). Effect size is negligible (Cohen's d=0.03).

### test_b_price_by_property_type
- **Test**: Kruskal-Wallis H | H0: Median asking_price is equal across all property types
- **Statistic**: 7.853, **p-value**: 0.09712622, **significant**: False
- **Effect size**: {'eta_squared': 0.0009, 'label': 'negligible'}
- **Interpretation**: Property type is not significantly associated with price (p=9.71e-02). Effect size eta²=0.001 (negligible).

### test_c_yield_by_property_type
- **Test**: Kruskal-Wallis H | H0: Median rental yield is equal across property types
- **Statistic**: 7.863, **p-value**: 0.09673, **significant**: False
- **Effect size**: {'eta_squared': 0.0008, 'label': 'negligible'}
- **Interpretation**: Rental yield does not differ significantly by property type (p=0.0967), effect size is negligible (eta²=0.0008).

### test_d_buyer_type_vs_transaction_type
- **Test**: Chi-square test of independence | H0: buyer_type and transaction_type are independent
- **Statistic**: 0.12, **p-value**: 0.94169, **significant**: False
- **Effect size**: {'cramers_v': 0.0025, 'label': 'negligible'}
- **Interpretation**: No significant association between buyer type and transaction type (p=0.9417, Cramér's V=0.002).

## 11. Key Business Insights

**Insight 1 (market_segmentation, confidence: high — based on full-population SQL aggregation, not a sample)**
- Bengaluru has the highest median asking price (₹13,227,000), 15.8% above the lowest-priced city, Chennai (₹11,418,000).
- *Implication*: City-level price dispersion is moderate (not extreme), suggesting the dataset doesn't have one dominant 'hot market' city — investment opportunity is more locality-driven than city-driven.
- *Action*: Prioritize locality-level analysis (not just city) when screening investment opportunities.

**Insight 2 (statistical_test, confidence: high — p-value and effect size both point the same direction)**
- Property type is NOT a statistically significant driver of price (Kruskal-Wallis p=0.097), explaining only 0.1% of price variance.
- *Implication*: Counter-intuitive: in this dataset, AREA (sqft) drives price far more than the property TYPE label (Apartment vs Villa vs Studio) — consistent with the strong area<->price correlation (r=0.837, see Insight 4).
- *Action*: Valuation models should weight area_sqft heavily and treat property_type as a secondary feature — consistent with what src/ml_valuation_model.py already found (area_sqft = 0.84 feature importance).

**Insight 3 (data_quality_critical, confidence: high — root cause traced to specific line of generator code, reproducible)**
- 8.34% of transactions are IQR-flagged as price outliers, traced to a runaway monthly-compounding bug in the price-growth formula — national avg price/sqft grew 10,818→51,141 (2020→2025), a statistically extreme YoY +90.8% in the final year alone.
- *Implication*: ML models trained on transaction_price-derived features (or a future model using raw transaction price as a target) would learn this runaway trend as real signal — a genuine leakage/bias risk for any model trained on the full 2020-2025 window without correction.
- *Action*: FIX AT SOURCE in Phase 3+: add a growth ceiling/mean-reversion term to the locality price-growth formula in data/generate_data_part2.py. Until fixed, prefer market_monthly.average_price_sqft (same bug, but at least aggregated) over raw transaction_price for any new model.

**Insight 4 (correlation, confidence: high — consistent with known data-generation logic)**
- area_sqft has the strongest correlation with asking_price of any feature pair (Pearson r=0.838).
- *Implication*: Confirms the valuation model's heavy reliance on area_sqft (84% feature importance) is well-founded, not an artifact of an under-featured model.
- *Action*: No action needed — this validates existing ML model design (src/ml_valuation_model.py).

**Insight 5 (segment_performance, confidence: medium — descriptive, not yet hypothesis-tested for statistical significance)**
- Sampath Constructions leads sales velocity at 93.3% (rating 4.9), vs Borra Constructions at only 68.3% (rating 2.0).
- *Implication*: Developer quality/delivery track record (correlated with rating by construction) is a meaningful differentiator in absorption — relevant to the Decision Engine's market_score component.
- *Action*: Decision Engine already incorporates developer signal indirectly via risk scoring — consider adding sales_velocity_pct as an explicit Decision Engine input in a future calibration phase.

**Insight 6 (statistical_test, confidence: high — p-value directly measured, not inferred)**
- Interest rate shows essentially zero correlation with demand_index in the cross-sectional data (Pearson r=-0.004, p=0.73, not significant) despite the data generator's formula explicitly reducing demand as interest rates rise.
- *Implication*: The interest-rate effect (coefficient -0.6 per point, see data/generate_data_part2.py) is small relative to other demand noise (std dev ~1.5/month) — it exists in the generator but is not statistically detectable in aggregate. A forecasting model would likely not find interest rate a useful demand predictor as currently generated.
- *Action*: If interest-rate sensitivity is meant to be a demonstrable feature of this platform, the generator's interest-rate coefficient should be strengthened in a future data-regeneration phase.

## 12. ML Feature Insights

- **[redundant_features / multicollinearity]** area_sqft <-> asking_price Pearson r=0.837; area_sqft <-> bedrooms r=0.830
  - area_sqft and bedrooms are highly correlated (r=0.83). The existing valuation model already uses both — fine for tree-based models (GradientBoostingRegressor, robust to multicollinearity) but would be a problem if a future linear/regularized model is added. Flag for Phase 3 if a linear baseline model is introduced.

- **[leakage_candidate / target_quality]** transaction_price and price_per_sqft show skewness=12.2, excess_kurtosis=172 (distributions.py), traced to a data-generation bug (outliers.py)
  - Any FUTURE model using raw transaction_price (not asking_price) as a target or feature will inherit the runaway-compounding artifact as if it were real signal. The existing valuation model correctly uses asking_price (not transaction_price) as its target — no change needed there. But if Phase 3+ adds a 'transaction-price prediction' model, it MUST either (a) wait for the generator fix, or (b) log-transform + winsorize price_per_sqft first.

- **[transformation_candidate]** properties.monthly_rent skewness=0.719 (right-skewed), properties.asking_price skewness=1.118 (strongly right-skewed)
  - Both targets are right-skewed, which is normal for price-like variables. GradientBoostingRegressor (used in rent_v1_gbr and valuation_v1_gbr) doesn't require normality, so this is NOT currently a problem. If a future model sensitive to target distribution (e.g. linear regression, neural net with MSE loss) is introduced, consider log1p-transforming the target first.

- **[confirmed_weak_signal]** listing_history.days_on_market outliers (0.42% IQR) show NEEDS_INVESTIGATION classification — consistent with the already-known weak DOM model (R²=-0.04)
  - This EDA phase independently confirms (via distribution shape + outlier analysis, not just the original model metrics) that days_on_market has no recoverable structure in the current dataset. Model Registry's REJECTED status for dom_v1_gbr remains correct and does not need re-evaluation. If DOM is fixed at the generator level (Phase 3+), re-run distributions.py + hypothesis_tests.py on the new data before re-training.

- **[low_value_feature]** property_type is NOT a significant price driver (Kruskal-Wallis p=0.097, eta²=0.001) but IS currently one-hot-encoded as a feature in valuation_v1_gbr
  - property_type contributes negligible signal beyond what area_sqft/bedrooms already capture (consistent with the model's own feature_importance ranking, where property_type dummies rank low). Not harmful to keep (tree-based model handles irrelevant features gracefully), but a candidate for removal if simplifying the feature set in Phase 3.

- **[strong_predictive_feature]** demand_index <-> units_sold r=0.881, demand_index <-> available_inventory r=-0.762 (market-level correlations)
  - demand_index is a strong, non-redundant predictor at the market level — already used as a feature in price_forecast_v1_gbr_6m and demand_forecast_v1_gbr_6m (both READY in the Model Registry, R²=0.78/0.92). This EDA confirms those models are using the right signal.

## 13. Limitations

- This report analyzes a **synthetic dataset** — findings describe generator behavior, not real real-estate markets.
- The transaction-price runaway-compounding bug (§9) means all price-growth figures in §8 should be treated as a generator artifact, not a market signal, until fixed at source.
- Hypothesis tests use a skewness/kurtosis heuristic for normality (not Shapiro-Wilk) because sample sizes (n>5000) make Shapiro over-sensitive to trivial deviations.
- No source data or existing ML models were modified in this phase (Phase 2 = analytics only).