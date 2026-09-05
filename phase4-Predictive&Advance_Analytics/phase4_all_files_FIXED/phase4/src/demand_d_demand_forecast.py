#!/usr/bin/env python
# coding: utf-8

# In[1]:


"""
Phase 4 -- Model D: Demand Forecasting (6-month horizon)
==========================================================
Target: locality-month demand_index, 6 months ahead.
Business question: "Is demand in this locality likely to strengthen or
weaken over the next 6 months?" Feeds the Decision Engine's market-momentum
component alongside Model C.

demand_index (0-100, bounded) does NOT carry the same compounding-growth bug
as average_price_sqft (Phase 3 EDA Section 5: demand_index skewness=-0.357,
"approximately symmetric" -- no heavy-tail artifact). No log-transform or
forced-status treatment is needed here; this model is evaluated on its own
merits under the normal promotion rule (Section 4.5).
"""
import os
import sys
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

sys.path.insert(0, os.getcwd())


from data_loader import build_locality_month_panel, RANDOM_STATE
from governance import ModelRegistry, regression_metrics

MODEL_NAME = "demand_forecast_v1_gbr_6m"
HORIZON = 6

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(""))), "models")

FEATURES = [
    "demand_index", "demand_lag1", "demand_lag3", "demand_roll3_avg",
    "supply_index", "average_price_sqft", "price_sqft_mom_growth",
    "units_sold_lag1", "absorption_lag1", "dom_lag1",
    "interest_rate", "mortgage_rate", "inflation", "income_growth",
    "average_income", "connectivity_score", "development_score", "commercial_score",
]
TEST_ORIGIN_CUTOFF = pd.Timestamp("2024-07-01")


def run():
    df = build_locality_month_panel().sort_values(["locality_id", "month"]).reset_index(drop=True)
    df["target_demand_fwd6"] = df.groupby("locality_id")["demand_index"].shift(-HORIZON)

    data = df.dropna(subset=["target_demand_fwd6"] + FEATURES).copy()
    train = data[data["month"] < TEST_ORIGIN_CUTOFF]
    test = data[data["month"] >= TEST_ORIGIN_CUTOFF]

    X_train, y_train = train[FEATURES], train["target_demand_fwd6"]
    X_test, y_test = test[FEATURES], test["target_demand_fwd6"]

    baseline_pred = test["demand_index"].values  # persistence
    baseline_metrics = regression_metrics(y_test, baseline_pred)

    model = GradientBoostingRegressor(
        n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=RANDOM_STATE,
    )
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    metrics = regression_metrics(y_test, pred)

    importances = pd.Series(model.feature_importances_, index=FEATURES).sort_values(ascending=False)
    top_features = importances.head(8).round(4).to_dict()

    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump({"model": model, "feature_columns": FEATURES}, os.path.join(MODELS_DIR, f"{MODEL_NAME}.joblib"))

    beats_baseline = metrics["r2"] > baseline_metrics["r2"]
    if metrics["r2"] >= 0.75 and beats_baseline:
        status = "PASS"
    elif metrics["r2"] >= 0.50 and beats_baseline:
        status = "PASS WITH LIMITATIONS"
    elif metrics["r2"] >= 0.50 and not beats_baseline:
        # High absolute R2 alone is not sufficient (Master Prompt 4.5: promotion
        # requires "useful baseline comparison"). Demand is highly autocorrelated,
        # so a trivial persistence baseline (demand in 6m = demand now) already
        # scores R2=0.933; this model's R2=0.932 does NOT beat it. Downgraded to
        # CONDITIONAL rather than PASS WITH LIMITATIONS so downstream consumers
        # (Phase 9 Prediction Agent) do not treat it as an approved, value-adding
        # forecast without an explicit human review gate.
        status = "CONDITIONAL"
    else:
        status = "REJECTED"

    reg = ModelRegistry()
    reg.register(
        model_name=MODEL_NAME,
        target=f"market_monthly.demand_index, {HORIZON} months ahead (locality-level)",
        features=FEATURES,
        training_data=f"market_monthly x economic_monthly x localities panel, "
                       f"train n={len(train)} (months < {TEST_ORIGIN_CUTOFF.date()}), "
                       f"test n={len(test)} (months >= {TEST_ORIGIN_CUTOFF.date()}, out-of-time)",
        validation_method="Out-of-time split: trained on earlier months, evaluated on the most "
                           "recent months. Compared against a persistence baseline "
                           "(demand in 6 months = demand now).",
        metrics=metrics,
        baseline={"persistence": baseline_metrics, "beats_persistence": bool(beats_baseline)},
        status=status,
        limitations=[
            "Trained on synthetic data; demand_index itself is a generator-defined composite, not "
            "an observed real-world index.",
            "Phase 3 EDA found interest_rate has a designed effect on demand in the generator "
            "(-0.6 per point) but this is NOT statistically detectable in the cross-sectional data "
            "(r=-0.004, p=0.73) -- interest_rate is included as a feature but may contribute little "
            "signal; kept for completeness/robustness rather than removed.",
            "New localities with fewer than 6 months of history cannot be scored.",
            "Status forced to CONDITIONAL rather than the higher tier its raw R2 would "
            "suggest: the model does not beat a trivial persistence baseline "
            "(model R2=" + str(metrics["r2"]) + " vs baseline R2=" + str(baseline_metrics["r2"]) +
            "). Treat as a candidate signal requiring human review before production use, "
            "not an approved, value-adding forecast.",
        ],
        business_use="Directional demand-momentum signal for the Decision Engine's market score "
                      "component (Phase 9) and for locality screening in Phase 8 (Geo Intelligence).",
        known_failure_cases=[
            "Localities with fewer than 6 months of history: INSUFFICIENT DATA.",
            "Demand shocks not present in the training window (e.g. a sudden new-infrastructure "
            "announcement) will not be anticipated -- the model extrapolates from historical "
            "patterns only.",
        ],
    )

    print(f"[{MODEL_NAME}] status={status}")
    print(f"  model   : {metrics}")
    print(f"  baseline: {baseline_metrics}")
    print(f"  top features: {top_features}")
    return {"status": status, "metrics": metrics, "baseline": baseline_metrics,
            "top_features": top_features, "n_train": len(train), "n_test": len(test)}


if __name__ == "__main__":
    run()



# In[ ]:



