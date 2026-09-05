#!/usr/bin/env python
# coding: utf-8

# In[3]:


"""
Phase 4 -- Model B: Rent Prediction
====================================
Target: properties.monthly_rent
Business question: "What monthly rent should this property command?" Feeds
Phase 6 financial engine (rental income line) when the user has not supplied
an assumed rent.

Leakage guard: asking_price is EXCLUDED as a feature for the same reason
Model A excludes monthly_rent -- see model_a_valuation.py docstring. Both
models are trained independently from structural/locational features only.
"""
import os
import sys
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import LinearRegression

sys.path.insert(0, os.getcwd())

from data_loader import (
    build_property_master, RANDOM_STATE,
    PROPERTY_STRUCTURAL_FEATURES, LOCALITY_FEATURES, PROJECT_DEVELOPER_FEATURES,
)
from governance import ModelRegistry, regression_metrics, improvement_vs_baseline, one_hot, object_columns

MODEL_NAME = "rent_v1_gbr"
TARGET = "monthly_rent"

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(""))), "models")

def run():
    df = build_property_master()
    features = PROPERTY_STRUCTURAL_FEATURES + LOCALITY_FEATURES + PROJECT_DEVELOPER_FEATURES
    data = df[features + [TARGET, "monthly_rent_was_imputed", "property_id"]].dropna(subset=[TARGET]).copy()

    assert TARGET not in features and "asking_price" not in features, "LEAKAGE check failed"

    # Per Phase 1 cleaning_report: 2% of monthly_rent values were median-imputed
    # (flag: monthly_rent_was_imputed). Training on imputed targets would teach
    # the model to reproduce a median-fill rule, not real rent signal -- exclude
    # those rows from training/evaluation rather than silently keeping them.
    n_imputed = int(data["monthly_rent_was_imputed"].sum())
    data = data[data["monthly_rent_was_imputed"] == False].copy()  # noqa: E712

    cat_cols = object_columns(data[features])
    num_cols = [c for c in features if c not in cat_cols]
    n_missing = data[features].isna().sum().sum()
    data[num_cols] = data[num_cols].fillna(data[num_cols].median(numeric_only=True))
    for c in cat_cols:
        data[c] = data[c].fillna("Unknown")

    X = one_hot(data[features], cat_cols)
    y = data[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=RANDOM_STATE)

    baseline_pred = np.full_like(y_test, fill_value=y_train.median(), dtype=float)
    baseline_metrics = regression_metrics(y_test, baseline_pred)

    lr = LinearRegression().fit(X_train, y_train)
    lr_metrics = regression_metrics(y_test, lr.predict(X_test))

    model = GradientBoostingRegressor(
        n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=RANDOM_STATE,
    )
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    metrics = regression_metrics(y_test, pred)

    residuals = y_test.values - pred
    residual_summary = {
        "mean_residual": round(float(np.mean(residuals)), 2),
        "std_residual": round(float(np.std(residuals)), 2),
        "pct_within_10pct_of_actual": round(float(np.mean(np.abs(residuals) / y_test.values <= 0.10) * 100), 1),
    }
    importances = pd.Series(model.feature_importances_, index=X.columns).sort_values(ascending=False)
    top_features = importances.head(10).round(4).to_dict()

    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump({"model": model, "feature_columns": list(X.columns)},
                os.path.join(MODELS_DIR, f"{MODEL_NAME}.joblib"))

    r2_gain_vs_linear = improvement_vs_baseline(metrics["r2"], lr_metrics["r2"], higher_is_better=True)
    if metrics["r2"] >= 0.80 and residual_summary["pct_within_10pct_of_actual"] >= 60:
        status = "PASS"
    elif metrics["r2"] >= 0.60:
        status = "PASS WITH LIMITATIONS"
    else:
        status = "REJECTED"

    reg = ModelRegistry()
    reg.register(
        model_name=MODEL_NAME,
        target=TARGET,
        features=list(X.columns),
        training_data=f"core.properties (rows where monthly_rent was NOT imputed) joined to "
                       f"projects/localities/cities/developers, n={len(data)} "
                       f"({n_imputed} imputed rows excluded from training/eval)",
        validation_method="Random 80/20 holdout split (seed=42); monthly_rent is a point-in-time "
                           "attribute (not a series in properties.csv), so temporal split is not "
                           "applicable -- documented, not omitted silently.",
        metrics={**metrics, **residual_summary},
        baseline={"naive_median": baseline_metrics, "linear_regression": lr_metrics,
                  "r2_gain_vs_linear_pct": r2_gain_vs_linear},
        status=status,
        limitations=[
            "Trained on synthetic data -- structure is realistic but not calibrated to a real market.",
            "asking_price intentionally excluded as a feature to avoid circularity with Model A "
            "(valuation); both models are trained independently on structural/location signal only.",
            f"{n_imputed} rows with generator-imputed monthly_rent (Phase 1 cleaning step) were "
            "excluded from training and evaluation to avoid learning an imputation rule as if it "
            "were real signal.",
            f"{n_missing} feature cells were missing and median/'Unknown'-imputed before training.",
        ],
        business_use="Screening-level rent estimate for Phase 6 financial engine income assumptions "
                      "when the user has not supplied an expected rent.",
        known_failure_cases=[
            "Localities/cities absent from training data cannot be scored -- INSUFFICIENT DATA at "
            "the agent layer.",
            "Furnishing-driven rent premiums may be under-fit if a furnishing category is rare in "
            "the training sample for a given locality.",
        ],
    )

    print(f"[{MODEL_NAME}] status={status}")
    print(f"  model : {metrics}")
    print(f"  linreg: {lr_metrics}")
    print(f"  naive : {baseline_metrics}")
    print(f"  residuals: {residual_summary}")
    print(f"  top features: {top_features}")
    return {"status": status, "metrics": metrics, "baseline": baseline_metrics,
            "linear_baseline": lr_metrics, "residuals": residual_summary,
            "top_features": top_features, "n_train": len(X_train), "n_test": len(X_test)}


if __name__ == "__main__":
    run()



# In[ ]:



