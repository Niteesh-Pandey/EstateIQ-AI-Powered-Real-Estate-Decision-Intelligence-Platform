"""
Phase 8 -- Testing (Master Prompt Section 12: Geo Tests -- location metrics,
scoring, missing location data).
Run: python3 -m pytest src/geo/test_phase8.py -q
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import pandas as pd
import pytest

from geo_data_loader import load_locality_geo_from_csv
from accessibility import compute_accessibility, compute_infrastructure_intelligence, compute_neighborhood_quality
from geo_risk import compute_geo_risk, _delivery_risk, _concentration_risk
from location_score import compute_location_score, _market_strength_score, WEIGHTS
from geo_engine import run_geo_engine

GEO_2 = load_locality_geo_from_csv(2)
GEO_1 = load_locality_geo_from_csv(1)


# --------------------------------------------------------------- data_loader
def test_locality_not_found_returns_insufficient_data():
    result = load_locality_geo_from_csv(999999)
    assert result["status"] == "INSUFFICIENT DATA"


def test_observed_scores_are_tagged_observed():
    assert GEO_2["governance"]["connectivity_score"] == "OBSERVED"
    assert GEO_2["observed_scores"]["connectivity_score"] is not None


def test_infrastructure_planned_vs_completed_split_is_consistent():
    inv = GEO_2["infrastructure_inventory"]
    assert inv["n_planned"] + inv["n_completed"] == inv["total_items"]


def test_market_intelligence_insufficient_when_no_locality_rows():
    from geo_data_loader import _market_intelligence
    empty = pd.DataFrame(columns=["locality_id", "month", "demand_index"])
    result = _market_intelligence(empty, 1)
    assert result["status"] == "INSUFFICIENT DATA"


# ------------------------------------------------------------- accessibility
def test_accessibility_insufficient_when_zero_infra_items():
    fake_geo = {"infrastructure_inventory": {"items": []}, "observed_scores": {}}
    result = compute_accessibility(fake_geo)
    assert result["status"] == "INSUFFICIENT DATA"


def test_accessibility_pass_with_limitations_when_partial_components():
    result = compute_accessibility(GEO_2)  # only Hospital records -> no transit/commercial
    assert result["status"] == "PASS WITH LIMITATIONS"
    assert "connectivity_score_observed" in result["components"]
    assert "transit_proximity_derived" not in result["components"]


def test_accessibility_score_never_exceeds_100():
    for lid in (1, 2):
        geo = load_locality_geo_from_csv(lid)
        result = compute_accessibility(geo)
        if result["accessibility_score"] is not None:
            assert 0 <= result["accessibility_score"] <= 100


def test_closer_infrastructure_increases_category_score():
    from accessibility import _category_access_score
    near = [{"type": "Metro", "impact_score": 80, "distance_from_center": 0.5}]
    far = [{"type": "Metro", "impact_score": 80, "distance_from_center": 10.0}]
    near_score = _category_access_score(near, {"Metro"})["score"]
    far_score = _category_access_score(far, {"Metro"})["score"]
    assert near_score > far_score


def test_infrastructure_intelligence_counts_match_inventory():
    result = compute_infrastructure_intelligence(GEO_2)
    assert result["total_infrastructure_items"] == GEO_2["infrastructure_inventory"]["total_items"]


def test_neighborhood_quality_income_ratio_computed_when_both_present():
    result = compute_neighborhood_quality(GEO_2)
    assert result["locality_income_vs_city_average_income_ratio"] is not None


# ------------------------------------------------------------------- geo_risk
def test_flood_and_environmental_risk_always_insufficient_data():
    """Master Prompt 8.7: never invent geo-risk values. This dataset has no
    hazard data at all -- these two must be INSUFFICIENT DATA for every
    locality, with no exceptions."""
    for lid in (1, 2, 3, 10, 50):
        geo = load_locality_geo_from_csv(lid)
        risk = compute_geo_risk(geo)
        assert risk["flood_risk"]["status"] == "INSUFFICIENT DATA"
        assert risk["environmental_risk"]["status"] == "INSUFFICIENT DATA"


def test_delivery_risk_insufficient_when_no_items():
    assert _delivery_risk([])["status"] == "INSUFFICIENT DATA"


def test_delivery_risk_100_when_all_planned():
    items = [{"impact_score": 50, "is_planned": True}, {"impact_score": 50, "is_planned": True}]
    result = _delivery_risk(items)
    assert result["score_0_100"] == 100.0


def test_delivery_risk_0_when_none_planned():
    items = [{"impact_score": 50, "is_planned": False}, {"impact_score": 50, "is_planned": False}]
    result = _delivery_risk(items)
    assert result["score_0_100"] == 0.0


def test_concentration_risk_single_item_is_maximum():
    result = _concentration_risk([{"impact_score": 70}])
    assert result["score_0_100"] == 100.0


def test_concentration_risk_even_split_is_low():
    items = [{"impact_score": 50}, {"impact_score": 50}, {"impact_score": 50}, {"impact_score": 50}]
    result = _concentration_risk(items)
    assert result["score_0_100"] < 10.0


def test_concentration_risk_uneven_split_is_higher_than_even():
    even = _concentration_risk([{"impact_score": 50}, {"impact_score": 50},
                                 {"impact_score": 50}, {"impact_score": 50}])
    uneven = _concentration_risk([{"impact_score": 97}, {"impact_score": 1},
                                   {"impact_score": 1}, {"impact_score": 1}])
    assert uneven["hhi"] > even["hhi"]


# --------------------------------------------------------------- location_score
def test_market_strength_score_bounded_0_100():
    for lid in range(1, 20):
        geo = load_locality_geo_from_csv(lid)
        s = _market_strength_score(geo["market_intelligence"])
        if s is not None:
            assert 0.0 <= s <= 100.0


def test_market_strength_not_saturated_across_portfolio():
    """Regression test for the normalization bug found during development:
    a naive cap-at-ratio=1.0 saturated 70/90 localities at 100. After the
    P5/P95 data-driven fix, no locality should be pinned at exactly 100."""
    saturated = 0
    total = 0
    for lid in range(1, 91):
        geo = load_locality_geo_from_csv(lid)
        s = _market_strength_score(geo["market_intelligence"])
        if s is not None:
            total += 1
            if s >= 99.9:
                saturated += 1
    assert total > 0
    assert saturated / total < 0.10  # fewer than 10% at the ceiling


def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_location_score_renormalizes_when_component_missing():
    acc = compute_accessibility(GEO_1)  # locality 1 has only 1 infra item, no transit/commercial
    result = compute_location_score(GEO_1, acc)
    assert abs(sum(result["weights_applied"].values()) - 1.0) < 1e-6


def test_location_score_insufficient_when_nothing_available():
    empty_geo = {"observed_scores": {}, "market_intelligence": {"status": "INSUFFICIENT DATA"}}
    empty_acc = {"accessibility_score": None}
    result = compute_location_score(empty_geo, empty_acc)
    assert result["status"] == "INSUFFICIENT DATA"


def test_location_score_bounded_0_100():
    for lid in (1, 2, 3, 10, 50):
        geo = load_locality_geo_from_csv(lid)
        acc = compute_accessibility(geo)
        result = compute_location_score(geo, acc)
        if result["location_score"] is not None:
            assert 0 <= result["location_score"] <= 100


# ------------------------------------------------------------------- geo_engine
def test_geo_engine_end_to_end_pass_status():
    result = run_geo_engine(2, source="csv")
    assert result["validation_status"] in ("PASS", "PASS WITH LIMITATIONS")
    assert result["location_score"]["location_score"] is not None


def test_geo_engine_insufficient_data_for_unknown_locality():
    result = run_geo_engine(999999, source="csv")
    assert result["validation_status"] == "INSUFFICIENT DATA"


def test_geo_engine_always_flags_flood_environmental_limitation():
    result = run_geo_engine(2, source="csv")
    assert any("flood_risk and environmental_risk" in note for note in result["limitations"])


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
