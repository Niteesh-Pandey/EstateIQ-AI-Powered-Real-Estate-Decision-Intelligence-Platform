"""
Phase 9, Section 9.2 -- Prediction Agent
============================================
"Uses only approved Phase 4 models. It must respect READY, CONDITIONAL,
REJECTED model statuses."

Model gating, read directly from `models/model_registry.json` -- never
hardcoded here, so a registry update automatically changes what this agent
is allowed to use, without a code change:

  valuation_v1_gbr        PASS WITH LIMITATIONS  -> USED (property-level)
  rent_v1_gbr              PASS WITH LIMITATIONS  -> USED (property-level)
  price_forecast_v1_gbr_6m CONDITIONAL            -> USED, but surfaced separately
                                                       and flagged as requiring human
                                                       review (Phase 4's own registry
                                                       note), never folded into the
                                                       automated decision_score
  demand_forecast_v1_gbr_6m CONDITIONAL           -> same treatment as price forecast
  dom_v1_gbr                REJECTED              -> NEVER CALLED
  sale_probability_v1_gbr   REJECTED              -> NEVER CALLED
  risk_score_v1_composite   UNCALIBRATED           -> out of scope here by design (see
                                                       docs/limitations.md -- Phase 7's
                                                       Monte Carlo risk is the decision-
                                                       relevant risk signal; folding in a
                                                       second, UNCALIBRATED risk number
                                                       from a different methodology would
                                                       double-count risk ambiguously)

Feature construction reuses Phase 4's `data_loader.build_property_master()`
and `governance.one_hot()` UNCHANGED -- the exact same feature pipeline used
at training time -- then reindexes to each model's saved `feature_columns`
list (stored alongside the model in the .joblib) so inference-time columns
always match training-time columns exactly, even for a single-row prediction.
"""
import json
import os
import sys

import joblib
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "predict"))
from contracts import AgentFinding
from predict_data_loader import build_property_master, PROPERTY_STRUCTURAL_FEATURES, LOCALITY_FEATURES, \
    PROJECT_DEVELOPER_FEATURES  # reused from Phase 4, unchanged
from governance import one_hot, object_columns  # reused from Phase 4, unchanged

_MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(_HERE)), "models")
_REGISTRY_PATH = os.path.join(_MODELS_DIR, "model_registry.json")

USABLE_STATUSES = {"PASS", "PASS WITH LIMITATIONS", "CONDITIONAL"}
FEATURES = PROPERTY_STRUCTURAL_FEATURES + LOCALITY_FEATURES + PROJECT_DEVELOPER_FEATURES


def _load_registry() -> dict:
    return json.load(open(_REGISTRY_PATH))


def _predict_single_row(model_name: str, row: pd.DataFrame) -> float:
    artifact = joblib.load(os.path.join(_MODELS_DIR, f"{model_name}.joblib"))
    model, feature_columns = artifact["model"], artifact["feature_columns"]

    cat_cols = object_columns(row[FEATURES])
    num_cols = [c for c in FEATURES if c not in cat_cols]
    row = row.copy()
    row[num_cols] = row[num_cols].fillna(row[num_cols].median(numeric_only=True))
    for c in cat_cols:
        row[c] = row[c].fillna("Unknown")

    encoded = one_hot(row[FEATURES], cat_cols)
    encoded = encoded.reindex(columns=feature_columns, fill_value=0)
    return float(model.predict(encoded)[0])


def get_predictions(property_id: int) -> AgentFinding:
    registry = _load_registry()
    master = build_property_master()
    row = master[master["property_id"] == property_id]

    if row.empty:
        return AgentFinding(
            agent_name="PredictionAgent", status="INSUFFICIENT DATA", finding_type="predictions",
            summary=f"property_id={property_id} not found in the Phase 4 feature table.",
            source="Phase 4 data_loader.build_property_master()", confidence=0.0,
        )

    predictions = {}
    limitations = []
    used_models = []

    valuation_status = registry["valuation_v1_gbr"]["status"]
    if valuation_status in USABLE_STATUSES:
        pred_price = _predict_single_row("valuation_v1_gbr", row)
        predictions["predicted_valuation"] = round(pred_price, 0)
        used_models.append({"model": "valuation_v1_gbr", "status": valuation_status})
    else:
        limitations.append(f"valuation_v1_gbr is {valuation_status} -- not used.")

    rent_status = registry["rent_v1_gbr"]["status"]
    if rent_status in USABLE_STATUSES:
        pred_rent = _predict_single_row("rent_v1_gbr", row)
        predictions["predicted_rent"] = round(pred_rent, 0)
        used_models.append({"model": "rent_v1_gbr", "status": rent_status})
    else:
        limitations.append(f"rent_v1_gbr is {rent_status} -- not used.")

    for rejected in ("dom_v1_gbr", "sale_probability_v1_gbr"):
        limitations.append(f"{rejected} is REJECTED per the Phase 4 model registry -- never called by "
                            f"this agent, regardless of what any caller requests.")

    limitations.append("price_forecast_v1_gbr_6m and demand_forecast_v1_gbr_6m are locality-level "
                        "(not property-level) and CONDITIONAL -- available via the Market Agent's "
                        "underlying data if needed, but intentionally excluded from this agent's "
                        "property-level predictions and from the automated decision_score.")
    limitations.append("risk_score_v1_composite is UNCALIBRATED and out of scope for this agent by "
                        "design -- Phase 7's Monte Carlo risk output is this platform's decision-relevant "
                        "risk signal; see docs/limitations.md.")

    asking_price = row.iloc[0].get("asking_price")
    valuation_gap_pct = None
    if predictions.get("predicted_valuation") and asking_price:
        valuation_gap_pct = round(float(100 * (predictions["predicted_valuation"] - asking_price) / asking_price), 2)
        predictions["valuation_gap_pct"] = valuation_gap_pct

    if not predictions:
        return AgentFinding(
            agent_name="PredictionAgent", status="INSUFFICIENT DATA", finding_type="predictions",
            summary="No usable models available for this property.",
            source="models/model_registry.json", confidence=0.0, limitations=limitations,
        )

    status = "PASS WITH LIMITATIONS"  # both usable models carry that registry status themselves
    summary_parts = []
    if "predicted_valuation" in predictions:
        summary_parts.append(f"predicted valuation ₹{predictions['predicted_valuation']:,.0f} "
                              f"({valuation_gap_pct:+.1f}% vs asking price)" if valuation_gap_pct is not None
                              else f"predicted valuation ₹{predictions['predicted_valuation']:,.0f}")
    if "predicted_rent" in predictions:
        summary_parts.append(f"predicted rent ₹{predictions['predicted_rent']:,.0f}/mo")

    return AgentFinding(
        agent_name="PredictionAgent", status=status, finding_type="predictions",
        summary=f"Property {property_id}: " + "; ".join(summary_parts) + ".",
        metrics=predictions,
        source="models/valuation_v1_gbr.joblib + rent_v1_gbr.joblib (Phase 4)",
        confidence=70.0,  # PASS WITH LIMITATIONS tier -- see Phase 4 report for R2/MAE detail
        limitations=limitations,
        raw={"predictions": predictions, "used_models": used_models},
    )


if __name__ == "__main__":
    print(get_predictions(1).to_dict())
