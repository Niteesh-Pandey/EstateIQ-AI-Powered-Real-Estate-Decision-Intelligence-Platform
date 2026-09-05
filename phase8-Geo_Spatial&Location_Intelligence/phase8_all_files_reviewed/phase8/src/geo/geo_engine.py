"""
Phase 8, Section 8.9 -- GeoResult
=====================================
Top-level entry point. Assembles every sub-module's output into the
structured `GeoResult` contract (location metrics, locality intelligence,
accessibility, infrastructure, geo risk, score, evidence, limitations).
Nothing is computed here directly -- this module only calls the other five
and packages their outputs, so there is exactly one place a caller (Phase 9's
Geo Agent) needs to call.
"""
import os
import sys


_HERE = os.getcwd()
sys.path.insert(0, _HERE)
#_HERE = os.path.dirname(os.path.abspath(__file__))
#sys.path.insert(0, _HERE)

from data_loader import load_locality_geo_from_csv, load_locality_geo_from_db
from accessibility import compute_accessibility, compute_infrastructure_intelligence, compute_neighborhood_quality
from geo_risk import compute_geo_risk
from location_score import compute_location_score


def run_geo_engine(locality_id: int, source: str = "csv") -> dict:
    loader = load_locality_geo_from_csv if source == "csv" else load_locality_geo_from_db
    geo_record = loader(locality_id)

    if geo_record.get("status") != "OK":
        return {
            "locality_id": locality_id,
            "validation_status": "INSUFFICIENT DATA",
            "reason": geo_record.get("reason"),
        }

    accessibility = compute_accessibility(geo_record)
    infrastructure = compute_infrastructure_intelligence(geo_record)
    neighborhood_quality = compute_neighborhood_quality(geo_record)
    geo_risk = compute_geo_risk(geo_record)
    location_score = compute_location_score(geo_record, accessibility)

    limitations = []
    if accessibility["status"] != "PASS":
        limitations.append("Accessibility score is based on partial infrastructure data for this locality "
                            "(missing transit and/or commercial infrastructure records) -- see "
                            "accessibility.components / accessibility.detail.")
    if location_score["status"] != "PASS":
        limitations.append(f"Location score weights were renormalized because these components were "
                            f"unavailable: {location_score.get('components_missing')}.")
    limitations.append("flood_risk and environmental_risk are INSUFFICIENT DATA for every locality in this "
                        "platform -- no hazard/environmental data source exists yet (see docs/limitations.md).")
    if geo_risk["infrastructure_delivery_risk"]["status"] == "INSUFFICIENT DATA":
        limitations.append("This locality has zero infrastructure records -- infrastructure-based risk and "
                            "accessibility sub-scores could not be computed.")

    return {
        "locality_id": locality_id,
        "validation_status": "PASS" if location_score["status"] == "PASS" and accessibility["status"] == "PASS"
                              else "PASS WITH LIMITATIONS",
        "locality_name": geo_record["locality_name"],
        "city": geo_record["city"],
        "state": geo_record["state"],
        "coordinates": geo_record["coordinates"],
        "locality_intelligence": {
            "market_intelligence": geo_record["market_intelligence"],
            "observed_scores": geo_record["observed_scores"],
        },
        "accessibility": accessibility,
        "infrastructure": infrastructure,
        "neighborhood_quality": neighborhood_quality,
        "geo_risk": geo_risk,
        "location_score": location_score,
        "evidence": {
            "sources": ["core.localities", "core.cities", "core.infrastructure", "core.market_monthly"],
            "governance": geo_record.get("governance", {}),
        },
        "limitations": limitations,
    }


if __name__ == "__main__":
    import json
    result = run_geo_engine(2, source="csv")
    print(json.dumps(result, indent=2, default=str))
