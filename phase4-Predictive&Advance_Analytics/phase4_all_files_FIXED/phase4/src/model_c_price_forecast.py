#!/usr/bin/env python
# coding: utf-8

# In[3]:


"""
Phase 4 -- Model C: Price Forecasting (6-month horizon)
=========================================================
Target: locality-month average_price_sqft, 6 months ahead of the "as of" month.
Business question: "Where is this locality's price/sqft likely headed over the
next 6 months?" Feeds the Decision Engine's market-momentum signal (Phase 9)
and Phase 6 exit-value assumptions.

*** CRITICAL DATA LIMITATION (Master Prompt Section 4.6) ***
Phase 3 EDA (Section 9 / Section 12) traced a data-generation bug: the
locality price-growth formula compounds monthly with no ceiling or
mean-reversion term, so market_monthly.average_price_sqft grows unrealistically
for high-demand localities (e.g. one locality: Rs 13,592/sqft in 2020-01 ->
Rs 1,923,519/sqft in 2025-12, a 141x increase). This was NOT fixed at source
because the original generator script is not part of the Phase 1/2/3
deliverables handed to Phase 4 (no generator code was supplied for
regeneration). Per Section 4.6's fallback ("if not possible, use a justified
transformation/robust treatment and clearly document the limitation"), this
model:
  1. Trains and evaluates in log-space (log1p of price/sqft) to dampen the
     exponential artifact's influence on the loss function.
  2. Uses a genuine out-of-time split (train on earlier months, test on the
     most recent, most-affected months) so the reported metrics reflect the
     model's real ability to forecast the (buggy) series -- not an optimistic
     in-sample fit.
  3. Is registered with status = CONDITIONAL, not PASS, regardless of the
     metric values obtained -- because the growth number this model forecasts
     is known to be partly a generator artifact rather than a real market
     signal. It must not be presented to a user as a real-world price
     forecast without this caveat attached (Section 7.7-style calibration
     rule, applied here to Phase 4 since Phase 4 precedes Phase 7).
"""
import os
import sys
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

sys.path.insert(0, os.getcwd())


from data_loader import build_locality_month_panel, RANDOM_STATE
from governance import ModelRegistry, regression_metrics, one_hot, object_columns

MODEL_NAME = "price_forecast_v1_gbr_6m"
HORIZON = 6

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(""))), "models")

FEATURES = [
    "average_price_sqft", "price_sqft_lag1", "price_sqft_lag3", "price_sqft_lag6",
    "price_sqft_mom_growth", "price_sqft_roll3_avg",
    "demand_index", "demand_lag1", "demand_lag3", "demand_roll3_avg",
    "supply_index", "units_sold_lag1", "absorption_lag1", "dom_lag1",
    "interest_rate", "mortgage_rate", "inflation", "income_growth",
    "average_income", "connectivity_score", "development_score",
]
TEST_ORIGIN_CUTOFF = pd.Timestamp("2024-07-01")  # out-of-time split


def run():
    df = build_locality_month_panel().sort_values(["locality_id", "month"]).reset_index(drop=True)

    # Target: log1p(price/sqft) HORIZON months ahead, within the same locality.
    df["target_price_sqft_fwd6"] = df.groupby("locality_id")["average_price_sqft"].shift(-HORIZON)
    df["log_target"] = np.log1p(df["target_price_sqft_fwd6"])
    for c in ["average_price_sqft", "price_sqft_lag1", "price_sqft_lag3", "price_sqft_lag6", "price_sqft_roll3_avg"]:
        df[f"log_{c}"] = np.log1p(df[c])

    log_features = [f"log_{c}" for c in
                    ["average_price_sqft", "price_sqft_lag1", "price_sqft_lag3", "price_sqft_lag6", "price_sqft_roll3_avg"]]
    other_features = [c for c in FEATURES if c not in
                       ["average_price_sqft", "price_sqft_lag1", "price_sqft_lag3", "price_sqft_lag6", "price_sqft_roll3_avg"]]
    all_features = log_features + other_features

    data = df.dropna(subset=["log_target"] + all_features).copy()

    train = data[data["month"] < TEST_ORIGIN_CUTOFF]
    test = data[data["month"] >= TEST_ORIGIN_CUTOFF]

    X_train, y_train = train[all_features], train["log_target"]
    X_test, y_test = test[all_features], test["log_target"]

    # Baseline: persistence forecast (log price/sqft in 6 months = log price/sqft now)
    baseline_pred_log = test["log_average_price_sqft"].values
    baseline_metrics_log = regression_metrics(y_test, baseline_pred_log)
    baseline_pred_actual = np.expm1(baseline_pred_log)
    baseline_metrics_actual = regression_metrics(np.expm1(y_test), baseline_pred_actual)

    model = GradientBoostingRegressor(
        n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=RANDOM_STATE,
    )
    model.fit(X_train, y_train)
    pred_log = model.predict(X_test)
    metrics_log = regression_metrics(y_test, pred_log)
    pred_actual = np.expm1(pred_log)
    metrics_actual = regression_metrics(np.expm1(y_test), pred_actual)

    importances = pd.Series(model.feature_importances_, index=all_features).sort_values(ascending=False)
    top_features = importances.head(8).round(4).to_dict()

    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump({"model": model, "feature_columns": all_features}, os.path.join(MODELS_DIR, f"{MODEL_NAME}.joblib"))

    # Beats-baseline check on the (more stable) log scale
    beats_baseline_log = metrics_log["r2"] > baseline_metrics_log["r2"]
    status = "CONDITIONAL"  # forced per docstring rationale, regardless of metric values

    reg = ModelRegistry()
    reg.register(
        model_name=MODEL_NAME,
        target=f"market_monthly.average_price_sqft, {HORIZON} months ahead (locality-level), "
               f"modeled in log1p space",
        features=all_features,
        training_data=f"market_monthly x economic_monthly x localities panel, "
                       f"train n={len(train)} (months < {TEST_ORIGIN_CUTOFF.date()}), "
                       f"test n={len(test)} (months >= {TEST_ORIGIN_CUTOFF.date()}, out-of-time)",
        validation_method="Out-of-time split: trained on earlier months, evaluated on the most "
                           "recent months (which are also the months most affected by the known "
                           "compounding bug -- see docstring). This is a genuine forecast "
                           "evaluation, not in-sample fit.",
        metrics={"log_space": metrics_log, "original_scale": metrics_actual},
        baseline={"persistence_log_space": baseline_metrics_log,
                  "persistence_original_scale": baseline_metrics_actual,
                  "beats_persistence_baseline_log_r2": bool(beats_baseline_log)},
        status=status,
        limitations=[
            "CRITICAL: market_monthly.average_price_sqft carries a known, traced data-generation "
            "bug (uncapped monthly compounding -- Phase 3 EDA Section 9/12). This model's target "
            "is therefore partly a generator artifact, not a real market signal. Forced status = "
            "CONDITIONAL regardless of R2/MAPE obtained.",
            "The original data generator script was not included in the Phase 1-3 deliverables "
            "provided to Phase 4, so 'fix at source and regenerate' (the preferred remedy per "
            "Section 4.6) was not possible in this phase. Log1p-transformation was used as the "
            "documented fallback treatment.",
            "MAPE on the original (non-log) scale can be extremely large for the small number of "
            "localities where the compounding effect is most severe -- report the log-space "
            "metrics as primary; original-scale metrics are provided for transparency, not as the "
            "headline number.",
            "Recommended follow-up: regenerate Phase 1 data with a growth ceiling/mean-reversion "
            "term, then retrain this model before any production use.",
        ],
        business_use="Directional (not point-precision) 6-month price/sqft momentum signal for the "
                      "Decision Engine's market-momentum component. Must be surfaced to users with "
                      "the CONDITIONAL caveat, never as a precise price target.",
        known_failure_cases=[
            "Localities exhibiting the extreme compounding pattern will have understated forecasts "
            "(the model partially, not fully, learns the exponential trend) -- systematic "
            "under-forecast risk in the highest-growth localities.",
            "New localities with fewer than 6 months of history cannot be scored (lag features "
            "undefined) -- INSUFFICIENT DATA at the agent layer.",
        ],
    )

    print(f"[{MODEL_NAME}] status={status} (forced CONDITIONAL -- see docstring)")
    print(f"  log-space   : {metrics_log}")
    print(f"  orig scale  : {metrics_actual}")
    print(f"  baseline log: {baseline_metrics_log}")
    print(f"  top features: {top_features}")
    return {"status": status, "metrics_log": metrics_log, "metrics_actual": metrics_actual,
            "baseline_log": baseline_metrics_log, "top_features": top_features,
            "n_train": len(train), "n_test": len(test)}


if __name__ == "__main__":
    run()


# In[ ]:



