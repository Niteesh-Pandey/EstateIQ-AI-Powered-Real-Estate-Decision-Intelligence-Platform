"""
Phase 8, Section 8.8 -- Location Score
==========================================
A transparent, documented composite (same governance standard as Phase 4's
Model G risk_score composite: "document variables, weights, normalization,
thresholds"). All 7 inputs are already 0-100 scale, so no further
normalization is applied before weighting.

DOCUMENTED WEIGHTS (equal-ish, business-judgement default -- no calibration
data exists in this platform to fit weights from actual investment outcomes
by locality, so this is stated as a starting default, not a fitted model):

  connectivity_score (OBSERVED)     15%
  safety_score (OBSERVED)           15%
  infrastructure_score (OBSERVED)   15%   <- Phase 1's own pre-computed score
  development_score (OBSERVED)      15%
  commercial_score (OBSERVED)       10%
  accessibility_score (DERIVED)     15%   <- Section 8.4, distance-weighted
  market_strength (DERIVED)         15%   <- Section 8.3, from market_monthly

If a component is unavailable, its weight is redistributed proportionally
across the remaining available components (not silently dropped or scored
as 0) and the result is `PASS WITH LIMITATIONS` rather than `PASS`, with
`components_used` / `components_missing` disclosed.
"""
WEIGHTS = {
    "connectivity_score": 0.15,
    "safety_score": 0.15,
    "infrastructure_score": 0.15,
    "development_score": 0.15,
    "commercial_score": 0.10,
    "accessibility_score": 0.15,
    "market_strength_score": 0.15,
}


def _market_strength_score(market_intel: dict) -> float:
    """DERIVED 0-100 composite from market_monthly: demand/supply balance
    and absorption rate, both already-observed indices from Phase 1/2.

    Normalization note: naive caps (e.g. "ratio=1.0 -> 100") were tried
    first and rejected -- checked against the full 90-locality distribution,
    median demand/supply ratio is 1.61 and median absorption_rate is 1.34,
    both already above 1.0 in this dataset's own convention, so a cap at 1.0
    saturated 70/90 localities at the maximum score and failed to
    differentiate anything. Normalization anchors below are instead the
    ACTUAL observed P5/P95 of each metric's "latest value per locality"
    across all 90 localities (computed once from market_monthly.csv):
      demand/supply ratio:  P5=1.06, P95=4.89
      absorption_rate:      P5=0.48, P95=6.21
    Values are min-max scaled between these anchors and clipped to [0,100]
    -- this is a documented, data-driven choice, not a fitted model (no
    target/outcome variable exists in this dataset to fit "strength" against)."""
    if market_intel.get("status") != "OBSERVED":
        return None
    demand = market_intel.get("mean_demand_index_last_12m")
    supply = market_intel.get("mean_supply_index_last_12m")
    absorption = market_intel.get("latest_absorption_rate")
    if demand is None or supply is None or absorption is None or supply == 0:
        return None

    ratio = demand / supply
    RATIO_P5, RATIO_P95 = 1.06, 4.89
    ABS_P5, ABS_P95 = 0.48, 6.21

    def scale(v, lo, hi):
        return max(0.0, min(100.0, 100.0 * (v - lo) / (hi - lo)))

    demand_supply_component = scale(ratio, RATIO_P5, RATIO_P95)
    absorption_component = scale(absorption, ABS_P5, ABS_P95)
    return round(0.6 * demand_supply_component + 0.4 * absorption_component, 1)


def compute_location_score(geo_record: dict, accessibility_result: dict) -> dict:
    scores = geo_record.get("observed_scores", {})
    market_intel = geo_record.get("market_intelligence", {})

    available = {}
    for key in ("connectivity_score", "safety_score", "infrastructure_score",
                "development_score", "commercial_score"):
        v = scores.get(key)
        if v is not None:
            available[key] = v

    if accessibility_result.get("accessibility_score") is not None:
        available["accessibility_score"] = accessibility_result["accessibility_score"]

    market_strength = _market_strength_score(market_intel)
    if market_strength is not None:
        available["market_strength_score"] = market_strength

    if not available:
        return {"status": "INSUFFICIENT DATA", "location_score": None}

    total_weight = sum(WEIGHTS[k] for k in available)
    renormalized = {k: WEIGHTS[k] / total_weight for k in available}
    location_score = round(sum(available[k] * renormalized[k] for k in available), 1)

    all_keys = set(WEIGHTS)
    missing = sorted(all_keys - set(available))
    status = "PASS" if not missing else "PASS WITH LIMITATIONS"

    return {
        "status": status,
        "location_score": location_score,
        "components_used": {k: round(v, 1) for k, v in available.items()},
        "weights_applied": {k: round(v, 3) for k, v in renormalized.items()},
        "components_missing": missing,
    }


if __name__ == "__main__":
    import json
    import os
    import sys

    sys.path.insert(0, os.getcwd())
    #sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from data_loader import load_locality_geo_from_csv
    from accessibility import compute_accessibility

    geo = load_locality_geo_from_csv(2)
    acc = compute_accessibility(geo)
    print(json.dumps(compute_location_score(geo, acc), indent=2))
