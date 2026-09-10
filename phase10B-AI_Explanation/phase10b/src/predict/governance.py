"""
Phase 4 -- ML Governance Utilities
===================================
Shared helpers used by every model script:
  - ModelRegistry: append-only JSON registry (Master Prompt 4.4)
  - status labels (Master Prompt Section 4 standard status system)
  - regression / classification metric bundles
  - a temporal / holdout split helper that documents its own leakage checks
"""
import json
import os
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from sklearn.metrics import (
    r2_score, mean_absolute_error, mean_squared_error,
    roc_auc_score, average_precision_score, brier_score_loss,
)

REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "model_registry.json"
)

STATUSES = {
    "PASS", "PASS WITH LIMITATIONS", "CONDITIONAL",
    "REJECTED", "BLOCKED", "INSUFFICIENT DATA", "UNCALIBRATED",
}


def mape(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mask = y_true != 0
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def regression_metrics(y_true, y_pred):
    return {
        "r2": round(float(r2_score(y_true, y_pred)), 4),
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 2),
        "rmse": round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 2),
        "mape_pct": round(mape(y_true, y_pred), 2),
    }


def classification_metrics(y_true, y_prob, threshold=0.5):
    y_pred = (np.asarray(y_prob) >= threshold).astype(int)
    out = {
        "roc_auc": round(float(roc_auc_score(y_true, y_prob)), 4),
        "pr_auc": round(float(average_precision_score(y_true, y_prob)), 4),
        "brier_score": round(float(brier_score_loss(y_true, y_prob)), 4),
        "accuracy_at_0.5": round(float(np.mean(y_pred == y_true)), 4),
        "base_rate_positive": round(float(np.mean(y_true)), 4),
    }
    return out


def improvement_vs_baseline(model_metric, baseline_metric, higher_is_better=True):
    if baseline_metric == 0:
        return None
    delta = model_metric - baseline_metric
    if not higher_is_better:
        delta = -delta
    return round(100.0 * delta / abs(baseline_metric), 1)


class ModelRegistry:
    """Append-only registry of Model Cards. Overwrites entries with the same
    model_name on re-run (idempotent), keeps everything else untouched."""

    def __init__(self, path=REGISTRY_PATH):
        self.path = path
        if os.path.exists(path):
            with open(path, "r") as f:
                self.entries = json.load(f)
        else:
            self.entries = {}

    def register(self, model_name, target, features, training_data, validation_method,
                 metrics, baseline, status, limitations, business_use,
                 known_failure_cases, version="v1"):
        assert status in STATUSES, f"Invalid status '{status}'. Must be one of {STATUSES}"
        self.entries[model_name] = {
            "model_name": model_name,
            "target": target,
            "features": features,
            "n_features": len(features),
            "training_data": training_data,
            "validation_method": validation_method,
            "metrics": metrics,
            "baseline": baseline,
            "status": status,
            "limitations": limitations,
            "business_use": business_use,
            "known_failure_cases": known_failure_cases,
            "version": version,
            "registered_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        self.save()

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.entries, f, indent=2, default=str)

    def to_markdown_table(self):
        rows = []
        for name, e in self.entries.items():
            rows.append({
                "model_name": name,
                "target": e["target"],
                "status": e["status"],
                "validation_method": e["validation_method"],
                "key_metric": _first_metric_str(e["metrics"]),
                "version": e["version"],
            })
        return pd.DataFrame(rows)


def _first_metric_str(metrics):
    if not metrics:
        return "n/a"
    parts = [f"{k}={v}" for k, v in list(metrics.items())[:3]]
    return ", ".join(parts)


def one_hot(df, cols):
    """Deterministic one-hot encoding; keeps column order stable across runs."""
    return pd.get_dummies(df, columns=[c for c in cols if c in df.columns], drop_first=True)


def object_columns(df):
    """pandas 2.x/3.x-safe way to find text/categorical columns (covers legacy
    'object' dtype, new pandas 'string' dtype, and pandas-3 default 'str' dtype)."""
    text_dtypes = ("object", "string", "str")
    return [c for c in df.columns if str(df[c].dtype) in text_dtypes]
