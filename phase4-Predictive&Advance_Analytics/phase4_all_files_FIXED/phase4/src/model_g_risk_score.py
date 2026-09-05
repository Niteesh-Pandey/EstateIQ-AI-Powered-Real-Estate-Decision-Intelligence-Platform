#!/usr/bin/env python
# coding: utf-8

# In[1]:


"""
Phase 4 -- Model G: Risk Score (Transparent Composite)
=========================================================
NOT a trained ML model. Per Master Prompt Section 3.4 ("scoring" must be
deterministic code, not LLM/black-box reasoning) and Section 4.2 ("If a
transparent composite is used, document: variables, weights, normalization,
thresholds"), this is a fully deterministic, auditable weighted composite.

It deliberately does NOT use Model E (days-on-market, REJECTED) or Model F
(sale probability, REJECTED) as inputs -- Phase 9's agent contract requires
respecting model statuses (READY/CONDITIONAL/REJECTED), and a REJECTED
model's output must not be laundered into a different score.

Components (property_id level), each normalized to a 0-100 risk sub-score
(higher = more risk):

  1. valuation_uncertainty_risk (weight 0.25)
     |asking_price - Model A predicted value| / asking_price, scaled to 0-100.
     Uses valuation_v1_gbr (status: PASS WITH LIMITATIONS) -- an approved,
     non-rejected model, consistent with the Prediction Agent contract.

  2. developer_risk (weight 0.20)
     Inverse composite of developer rating, delivery_score, quality_score,
     track_record (min-max normalized, then inverted: 100 - score).

  3. locality_quality_risk (weight 0.20)
     Inverse composite of locality safety_score, infrastructure_score,
     development_score, connectivity_score.

  4. market_liquidity_risk (weight 0.20)
     From the property's locality's MOST RECENT market_monthly row:
     low absorption_rate + high average_days_on_market + low demand_index
     relative to supply_index => higher risk.

  5. price_volatility_risk (weight 0.15)
     Rolling 12-month volatility (std of MoM growth) of the locality's
     average_price_sqft. Deliberately includes localities affected by the
     Phase 3 EDA compounding bug (Model C's CONDITIONAL caveat) -- for THIS
     component, unusually high volatility is treated as a genuine risk
     signal regardless of its cause, which is a defensible interpretation
     (a buyer cannot rely on gains that came from a data artifact any more
     than from real volatility).

Status: UNCALIBRATED. This composite has not been validated against real
historical investment outcomes (no ground-truth "was this actually risky"
label exists in a synthetic dataset). Per the spirit of Section 7.7, an
uncalibrated score's numeric value must never be presented as a real-world
probability of loss -- only as a relative ranking tool (compare properties
to each other), which is how it is documented for downstream use.
"""
import os
import sys
import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, os.getcwd())

from data_loader import build_property_master, build_locality_month_panel
from governance import ModelRegistry

MODEL_NAME = "risk_score_v1_composite"
MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(""))), "models")

WEIGHTS = {
    "valuation_uncertainty_risk": 0.25,
    "developer_risk": 0.20,
    "locality_quality_risk": 0.20,
    "market_liquidity_risk": 0.20,
    "price_volatility_risk": 0.15,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

RISK_BANDS = [(0, 30, "LOW"), (30, 55, "MODERATE"), (55, 75, "ELEVATED"), (75, 100, "HIGH")]


def _minmax_0_100(s):
    lo, hi = s.min(), s.max()
    if hi - lo < 1e-9:
        return pd.Series(50.0, index=s.index)  # no spread -> neutral midpoint, not invented extremes
    return 100.0 * (s - lo) / (hi - lo)


def band(score):
    for lo, hi, label in RISK_BANDS:
        if lo <= score < hi or (label == "HIGH" and score >= 75):
            return label
    return "HIGH"


def run():
    valuation_art = joblib.load(os.path.join(MODELS_DIR, "valuation_v1_gbr.joblib"))
    v_model, v_cols = valuation_art["model"], valuation_art["feature_columns"]

    from data_loader import PROPERTY_STRUCTURAL_FEATURES, LOCALITY_FEATURES, PROJECT_DEVELOPER_FEATURES
    from governance import one_hot, object_columns

    props = build_property_master()
    feat_cols = PROPERTY_STRUCTURAL_FEATURES + LOCALITY_FEATURES + PROJECT_DEVELOPER_FEATURES
    work = props.copy()
    cat_cols = object_columns(work[feat_cols])
    num_cols = [c for c in feat_cols if c not in cat_cols]
    work[num_cols] = work[num_cols].fillna(work[num_cols].median(numeric_only=True))
    for c in cat_cols:
        work[c] = work[c].fillna("Unknown")
    X = one_hot(work[feat_cols], cat_cols)
    X = X.reindex(columns=v_cols, fill_value=0)  # align to training-time columns
    work["predicted_value"] = v_model.predict(X)
    work["valuation_gap_pct"] = (work["asking_price"] - work["predicted_value"]).abs() / work["asking_price"] * 100

    # Component 1
    r1 = _minmax_0_100(work["valuation_gap_pct"].clip(upper=work["valuation_gap_pct"].quantile(0.99)))

    # Component 2: developer risk (inverse of quality signals)
    dev_quality = (
        _minmax_0_100(work["developer_rating"]) +
        _minmax_0_100(work["developer_delivery_score"]) +
        _minmax_0_100(work["developer_quality_score"]) +
        _minmax_0_100(work["developer_track_record"])
    ) / 4.0
    r2 = 100 - dev_quality

    # Component 3: locality quality risk (inverse)
    loc_quality = (
        _minmax_0_100(work["safety_score"]) +
        _minmax_0_100(work["infrastructure_score"]) +
        _minmax_0_100(work["development_score"]) +
        _minmax_0_100(work["connectivity_score"])
    ) / 4.0
    r3 = 100 - loc_quality

    # Component 4 & 5: latest locality market state + price volatility
    panel = build_locality_month_panel().sort_values(["locality_id", "month"])
    latest = panel.groupby("locality_id").tail(1).set_index("locality_id")
    vol = panel.groupby("locality_id")["price_sqft_mom_growth"].apply(
        lambda s: s.tail(12).std()
    )
    latest = latest.assign(price_vol=vol)

    liquidity_component = (
        (100 - _minmax_0_100(latest["absorption_rate"])) * 0.4 +
        _minmax_0_100(latest["average_days_on_market"]) * 0.3 +
        (100 - _minmax_0_100(latest["demand_index"] - latest["supply_index"])) * 0.3
    )
    latest["market_liquidity_risk"] = liquidity_component
    latest["price_volatility_risk"] = _minmax_0_100(latest["price_vol"].fillna(latest["price_vol"].median()))

    work = work.merge(
        latest[["market_liquidity_risk", "price_volatility_risk"]],
        left_on="locality_id", right_index=True, how="left",
    )

    work["valuation_uncertainty_risk"] = r1.values
    work["developer_risk"] = r2.values
    work["locality_quality_risk"] = r3.values

    work["risk_score"] = (
        work["valuation_uncertainty_risk"] * WEIGHTS["valuation_uncertainty_risk"] +
        work["developer_risk"] * WEIGHTS["developer_risk"] +
        work["locality_quality_risk"] * WEIGHTS["locality_quality_risk"] +
        work["market_liquidity_risk"] * WEIGHTS["market_liquidity_risk"] +
        work["price_volatility_risk"] * WEIGHTS["price_volatility_risk"]
    ).round(2)
    work["risk_band"] = work["risk_score"].apply(band)

    out_cols = ["property_id", "valuation_uncertainty_risk", "developer_risk",
                "locality_quality_risk", "market_liquidity_risk", "price_volatility_risk",
                "risk_score", "risk_band"]
    result = work[out_cols].round(2)

    os.makedirs(MODELS_DIR, exist_ok=True)
    result.to_csv(os.path.join(MODELS_DIR, "risk_score_v1_output.csv"), index=False)

    band_dist = result["risk_band"].value_counts(normalize=True).round(3).mul(100).to_dict()
    summary_stats = {
        "n_scored": len(result),
        "mean_risk_score": round(float(result["risk_score"].mean()), 2),
        "median_risk_score": round(float(result["risk_score"].median()), 2),
        "band_distribution_pct": band_dist,
    }

    reg = ModelRegistry()
    reg.register(
        model_name=MODEL_NAME,
        target="risk_score (0-100 composite, higher = more risk); risk_band "
               "(LOW/MODERATE/ELEVATED/HIGH)",
        features=list(WEIGHTS.keys()),
        training_data=f"Deterministic composite over property_master + locality_month_panel, "
                       f"n={len(result)} properties scored. Not a trained/fitted model -- weights "
                       f"are fixed business rules, not learned parameters.",
        validation_method="No train/test split (not a fitted model). Internal consistency checks: "
                           "each sub-component min-max normalized to 0-100 on the current dataset; "
                           "weights sum to 1.0 (assert in code); output distribution inspected for "
                           "sanity (band_distribution below).",
        metrics=summary_stats,
        baseline=None,
        status="UNCALIBRATED",
        limitations=[
            "This composite has NOT been validated against real historical investment "
            "outcomes -- there is no ground-truth 'was this property/locality actually risky' "
            "label in a synthetic dataset to calibrate against.",
            "Weights (0.25 / 0.20 / 0.20 / 0.20 / 0.15) are business judgment, not statistically "
            "fitted -- documented explicitly rather than presented as learned/optimal.",
            "Min-max normalization is dataset-relative: the LOWEST-risk property in this dataset "
            "still gets some non-zero-relative score if all properties in a given city/locality "
            "are structurally similar. Scores are a RELATIVE ranking tool, not an absolute "
            "probability of loss.",
            "Deliberately excludes Model E (dom_v1_gbr, REJECTED) and Model F "
            "(sale_probability_v1_gbr, REJECTED) as direct inputs, per the Phase 9 agent contract "
            "rule that rejected model outputs must not be consumed downstream.",
            "price_volatility_risk inherits Model C's known data-generation-bug caveat for the "
            "minority of localities with runaway compounding (Phase 3 EDA Section 9) -- see Model "
            "C's registry entry.",
        ],
        business_use="Relative risk ranking of properties for the Decision Engine's risk-score "
                      "component (Phase 9) and as an input candidate to Phase 7's Monte Carlo risk "
                      "driver identification. Must be presented to users as a RANKING, never as a "
                      "calibrated probability, until backtested against real outcomes.",
        known_failure_cases=[
            "Properties in a locality with only one project/developer will show artificially "
            "compressed developer_risk/locality_quality_risk spread (min-max normalization has "
            "little to work with in a small comparison set).",
            "New localities added after this run require re-computation (min-max bounds are "
            "computed over the current dataset snapshot, not fixed constants).",
        ],
    )

    print(f"[{MODEL_NAME}] status=UNCALIBRATED")
    print(f"  {summary_stats}")
    return {"status": "UNCALIBRATED", "summary": summary_stats}


if __name__ == "__main__":
    run()



# In[ ]:



