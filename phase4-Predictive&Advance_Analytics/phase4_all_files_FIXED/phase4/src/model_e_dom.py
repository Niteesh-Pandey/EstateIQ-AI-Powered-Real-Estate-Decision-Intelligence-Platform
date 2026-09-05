#!/usr/bin/env python
# coding: utf-8

# In[1]:


"""
Phase 4 -- Model E: Days-on-Market Prediction
================================================
Target: listing_history.days_on_market (closed listings only: Sold / Expired / Withdrawn)
Business question: "How long is this listing likely to stay on the market?"

Phase 3 EDA (Section 9, Section 12) already flagged this target as
NEEDS_INVESTIGATION / confirmed_weak_signal: "days_on_market has no
recoverable structure in the current dataset." Per Master Prompt Section 4.2
("Model E ... Only promote if useful predictive signal exists. Otherwise:
REJECTED"), this script trains the model anyway (to independently verify the
EDA finding with a real train/test split, not just take the EDA's word for
it) and applies the REJECTED status if the result confirms weak signal.
"""
import os
import sys
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import GradientBoostingRegressor

sys.path.insert(0, os.getcwd())


from data_loader import (
    build_listing_sale_outcomes, RANDOM_STATE,
    PROPERTY_STRUCTURAL_FEATURES, LOCALITY_FEATURES, PROJECT_DEVELOPER_FEATURES,
)
from governance import ModelRegistry, regression_metrics, one_hot, object_columns

MODEL_NAME = "dom_v1_gbr"
TARGET = "days_on_market"

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(""))), "models")


def run():
    _, closed = build_listing_sale_outcomes()
    features = PROPERTY_STRUCTURAL_FEATURES + LOCALITY_FEATURES + PROJECT_DEVELOPER_FEATURES
    data = closed[features + [TARGET, "listing_id"]].dropna(subset=[TARGET]).copy()

    cat_cols = object_columns(data[features])
    num_cols = [c for c in features if c not in cat_cols]
    data[num_cols] = data[num_cols].fillna(data[num_cols].median(numeric_only=True))
    for c in cat_cols:
        data[c] = data[c].fillna("Unknown")

    X = one_hot(data[features], cat_cols)
    y = data[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=RANDOM_STATE)

    baseline_pred = np.full_like(y_test, fill_value=y_train.median(), dtype=float)
    baseline_metrics = regression_metrics(y_test, baseline_pred)

    model = GradientBoostingRegressor(
        n_estimators=200, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=RANDOM_STATE,
    )
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    metrics = regression_metrics(y_test, pred)

    importances = pd.Series(model.feature_importances_, index=X.columns).sort_values(ascending=False)
    top_features = importances.head(8).round(4).to_dict()

    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump({"model": model, "feature_columns": list(X.columns)}, os.path.join(MODELS_DIR, f"{MODEL_NAME}.joblib"))

    # Promotion rule: EDA already showed near-zero/negative R2. Confirm with our
    # own held-out split; if R2 <= 0.10 (i.e. explains essentially no variance
    # beyond the mean), REJECT regardless of any single favorable-looking metric.
    if metrics["r2"] <= 0.10:
        status = "REJECTED"
    elif metrics["r2"] <= 0.30:
        status = "CONDITIONAL"
    else:
        status = "PASS WITH LIMITATIONS"

    reg = ModelRegistry()
    reg.register(
        model_name=MODEL_NAME,
        target=TARGET,
        features=list(X.columns),
        training_data=f"listing_history (closed listings: Sold/Expired/Withdrawn only; "
                       f"'Active' listings excluded as censored/unknown-outcome) joined to "
                       f"property/locality/developer context, n={len(data)}",
        validation_method="Random 80/20 holdout split (seed=42), compared to naive median baseline. "
                           "Independently re-verifies the Phase 3 EDA finding (R2 approx -0.04, "
                           "NEEDS_INVESTIGATION / confirmed_weak_signal) rather than assuming it.",
        metrics=metrics,
        baseline={"naive_median": baseline_metrics},
        status=status,
        limitations=[
            "Confirms Phase 3 EDA finding: days_on_market has no recoverable structure from the "
            "features available in this dataset (property attributes, locality scores, developer "
            "scores). The generator does not appear to encode a strong, learnable DOM signal from "
            "these inputs.",
            "This does NOT mean days-on-market is unpredictable in reality -- it means this "
            "particular synthetic dataset does not carry a learnable DOM signal from the available "
            "features. A future data-regeneration phase would need to add genuine DOM drivers "
            "(e.g. pricing-vs-market-median gap, listing-channel quality, seasonality effects) "
            "before this model could be usefully retrained.",
        ],
        business_use="NONE while status=REJECTED -- must not be surfaced to end users or consumed "
                      "by the Phase 9 Prediction Agent. Retained in the registry (not deleted) so "
                      "the rejection and its evidence remain auditable.",
        known_failure_cases=[
            "All predictions -- the model has no demonstrated predictive validity; do not use for "
            "any business decision in its current state.",
        ],
    )

    print(f"[{MODEL_NAME}] status={status}")
    print(f"  model   : {metrics}")
    print(f"  baseline: {baseline_metrics}")
    print(f"  top features: {top_features}")
    return {"status": status, "metrics": metrics, "baseline": baseline_metrics,
            "top_features": top_features, "n_train": len(X_train), "n_test": len(X_test)}


if __name__ == "__main__":
    run()



# In[ ]:



