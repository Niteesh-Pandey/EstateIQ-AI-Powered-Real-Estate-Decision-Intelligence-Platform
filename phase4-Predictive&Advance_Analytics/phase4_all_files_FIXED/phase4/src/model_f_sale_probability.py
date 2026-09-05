#!/usr/bin/env python
# coding: utf-8

# In[1]:


"""
Phase 4 -- Model F: Sale Probability
======================================
Target: listing_history status, binarized (Sold=1, Expired/Withdrawn=0), for
closed listings only. 'Active' listings are censored (outcome not yet known)
and are excluded from training/evaluation, not treated as either class.

Business question: "How likely is this listing to actually sell, vs expire /
be withdrawn?" Feeds the Decision Engine's liquidity/exit-risk signal.
"""
import os
import sys
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import calibration_curve


sys.path.insert(0, os.getcwd())

from data_loader import (
    build_listing_sale_outcomes, RANDOM_STATE,
    PROPERTY_STRUCTURAL_FEATURES, LOCALITY_FEATURES, PROJECT_DEVELOPER_FEATURES,
)
from governance import ModelRegistry, classification_metrics, one_hot, object_columns

MODEL_NAME = "sale_probability_v1_gbr"
TARGET = "sold_flag"
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

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )

    # Baseline: constant prediction at the training base rate
    base_rate = y_train.mean()
    baseline_prob = np.full(len(y_test), base_rate)
    baseline_metrics = classification_metrics(y_test, baseline_prob)

    lr = LogisticRegression(max_iter=1000).fit(X_train, y_train)
    lr_prob = lr.predict_proba(X_test)[:, 1]
    lr_metrics = classification_metrics(y_test, lr_prob)

    model = GradientBoostingClassifier(
        n_estimators=250, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=RANDOM_STATE,
    )
    model.fit(X_train, y_train)
    prob = model.predict_proba(X_test)[:, 1]
    metrics = classification_metrics(y_test, prob)

    # Calibration check (Master Prompt 4.3: "calibration")
    frac_pos, mean_pred = calibration_curve(y_test, prob, n_bins=10, strategy="quantile")
    calibration_gap = float(np.mean(np.abs(frac_pos - mean_pred)))

    importances = pd.Series(model.feature_importances_, index=X.columns).sort_values(ascending=False)
    top_features = importances.head(8).round(4).to_dict()

    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump({"model": model, "feature_columns": list(X.columns)}, os.path.join(MODELS_DIR, f"{MODEL_NAME}.joblib"))

    if metrics["roc_auc"] >= 0.70 and calibration_gap <= 0.10:
        status = "PASS"
    elif metrics["roc_auc"] >= 0.60:
        status = "PASS WITH LIMITATIONS"
    else:
        status = "REJECTED"

    reg = ModelRegistry()
    reg.register(
        model_name=MODEL_NAME,
        target="listing_history.status binarized (Sold=1 vs Expired/Withdrawn=0); "
               "'Active' listings excluded (censored outcome)",
        features=list(X.columns),
        training_data=f"listing_history (closed listings only) joined to property/locality/developer "
                       f"context, n={len(data)}, base rate (sold)={round(float(base_rate), 3)}",
        validation_method="Stratified random 80/20 holdout split (seed=42). Compared to a constant "
                           "base-rate baseline and a logistic regression baseline. Calibration "
                           "assessed via 10-bin quantile calibration curve.",
        metrics={**metrics, "calibration_gap": round(calibration_gap, 4)},
        baseline={"constant_base_rate": baseline_metrics, "logistic_regression": lr_metrics},
        status=status,
        limitations=[
            "Trained on synthetic data; 'sold' outcome is generator-determined, not from a real "
            "market.",
            "'Active' (still-open) listings are excluded from training as their true outcome is not "
            "yet known -- the model has not seen the most recent listings and may not reflect very "
            "recent market shifts.",
            "Sale probability here reflects whether a listing SOLD at all before "
            "expiring/withdrawal, not the probability of selling within any specific time window.",
        ],
        business_use="Liquidity/exit-risk signal for the Decision Engine (Phase 9) -- a property in "
                      "a locality/segment with historically low sale-through probability increases "
                      "exit risk in the financial and risk intelligence layers (Phase 6/7).",
        known_failure_cases=[
            "Listings in localities/segments rare in the training data will have less reliable "
            "probability estimates.",
            "Model does not account for listing price relative to market (asking_price is not a "
            "feature here to keep this model consistent with -- and independent of -- Model A's "
            "valuation-gap signal, which is a separate, dedicated feature in the Decision Engine).",
        ],
    )

    print(f"[{MODEL_NAME}] status={status}")
    print(f"  model   : {metrics}, calibration_gap={round(calibration_gap,4)}")
    print(f"  logreg  : {lr_metrics}")
    print(f"  baseline: {baseline_metrics}")
    print(f"  top features: {top_features}")
    return {"status": status, "metrics": metrics, "baseline": baseline_metrics,
            "logistic_baseline": lr_metrics, "calibration_gap": calibration_gap,
            "top_features": top_features, "n_train": len(X_train), "n_test": len(X_test)}


if __name__ == "__main__":
    run()



# In[ ]:



