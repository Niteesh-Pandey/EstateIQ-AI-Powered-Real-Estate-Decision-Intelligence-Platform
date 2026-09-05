"""
Phase 8, Section 8.4 (Accessibility) & 8.5 (Infrastructure) & 8.6 (Neighborhood Quality)
============================================================================================
Every score here is either consumed directly from Phase 1's `core.localities`
(already-validated 0-100 scores, tagged OBSERVED) or derived from
`core.infrastructure`'s real distance/impact_score fields using a documented,
inverse-distance-weighted formula (tagged DERIVED). Nothing is invented --
if a locality has zero infrastructure records of a given type, that
sub-component is INSUFFICIENT DATA and weights renormalize rather than
silently scoring it as 0 (which would unfairly penalize a locality just for
having sparse data, not necessarily poor access).
"""
import numpy as np

TRANSIT_TYPES = {"Metro", "Highway", "Airport"}
SOCIAL_TYPES = {"School", "Hospital"}
COMMERCIAL_TYPES = {"Mall", "Business District"}

# Proximity decay: an infra item's contribution to an access score falls off
# with distance. 1 / (1 + distance_km) is a simple, monotonic, bounded-at-1
# decay -- documented choice, not fitted to any observed travel-time data
# (none exists in this dataset).
#def _proximity_weight(distance_km: float) -> float:
   # return 1.0 / (1.0 + max(0.0, distance_km))
def _proximity_weight(distance_km: float) -> float:
    return 1.0 / (1.0 + max(0.0, float(distance_km)))

#def _category_access_score(items: list, types: set) -> dict:
    #relevant = [i for i in items if i["type"] in types]
   # if not relevant:
      #  return {"status": "INSUFFICIENT DATA", "score": None, "n_items": 0}

     # Change this line:
     #weighted = [float(i["impact_score"]) * _proximity_weight(i["distance_from_center"]) for i in relevant]   
    #weighted = [i["impact_score"] * _proximity_weight(i["distance_from_center"]) for i in relevant]
    # Normalize: max possible per-item contribution is impact_score=100 at distance=0 (weight=1) -> 100.
    # Score = mean weighted contribution, capped at 100.
    #score = min(100.0, float(np.mean(weighted)))
   # return {"status": "DERIVED", "score": round(score, 1), "n_items": len(relevant),
           # "nearest_distance_km": round(min(i["distance_from_center"] for i in relevant), 2)}
def _category_access_score(items, types):
    relevant = [i for i in items if i.get("type") in types]
    if not relevant:
        return {"status": "INSUFFICIENT DATA", "score": None, "n_items": 0}
    weighted = [float(i["impact_score"]) * _proximity_weight(i["distance_from_center"]) for i in relevant]
    score = min(100.0, float(np.mean(weighted)))
    return {"status": "OK", "score": score, "n_items": len(relevant)}

def compute_accessibility(geo_record: dict) -> dict:
    """Section 8.4. Combines OBSERVED connectivity_score with a DERIVED
    transit-proximity score computed from real infrastructure distances."""
    items = geo_record.get("infrastructure_inventory", {}).get("items", [])
    connectivity_observed = geo_record.get("observed_scores", {}).get("connectivity_score")
    transit = _category_access_score(items, TRANSIT_TYPES)
    commercial_access = _category_access_score(items, COMMERCIAL_TYPES)

    components = {}
    if connectivity_observed is not None:
        components["connectivity_score_observed"] = connectivity_observed
    if transit["score"] is not None:
        components["transit_proximity_derived"] = transit["score"]
    if commercial_access["score"] is not None:
        components["commercial_proximity_derived"] = commercial_access["score"]

    if not components:
        return {"status": "INSUFFICIENT DATA", "accessibility_score": None,
                "components": {}, "detail": {"transit": transit, "commercial_access": commercial_access}}

    # Equal weighting across whatever components are actually available --
    # documented as the simplest defensible default when component-specific
    # weights aren't independently justified (no business input received on
    # relative importance of connectivity vs. transit proximity vs. commercial
    # proximity for this platform).
    accessibility_score = round(float(np.mean(list(components.values()))), 1)
    status = "PASS" if len(components) == 3 else "PASS WITH LIMITATIONS"

    return {
        "status": status,
        "accessibility_score": accessibility_score,
        "components": components,
        "detail": {"transit": transit, "commercial_access": commercial_access},
    }


def compute_infrastructure_intelligence(geo_record: dict) -> dict:
    """Section 8.5. Social/transit/commercial infrastructure sub-scores,
    each an inverse-distance-weighted composite of that category's real
    infrastructure records (same formula as accessibility, applied to the
    social-infrastructure category here)."""
    items = geo_record.get("infrastructure_inventory", {}).get("items", [])
    social = _category_access_score(items, SOCIAL_TYPES)
    transit = _category_access_score(items, TRANSIT_TYPES)
    commercial = _category_access_score(items, COMMERCIAL_TYPES)

    inventory = geo_record.get("infrastructure_inventory", {})
    return {
        "social_infrastructure": social,
        "transit_infrastructure": transit,
        "commercial_infrastructure": commercial,
        "total_infrastructure_items": inventory.get("total_items", 0),
        "n_planned": inventory.get("n_planned", 0),
        "n_completed": inventory.get("n_completed", 0),
        "by_type_counts": {k: v["count"] for k, v in inventory.get("by_type", {}).items()},
    }


def compute_neighborhood_quality(geo_record: dict) -> dict:
    """Section 8.6. Directly surfaces the OBSERVED demographic/quality
    signals Phase 1 already validated -- no re-derivation, just assembled
    into the GeoResult's neighborhood-quality view."""
    scores = geo_record.get("observed_scores", {})
    demo = geo_record.get("demographics", {})
    city_ctx = geo_record.get("city_context", {})

    fields = {
        "safety_score": scores.get("safety_score"),
        "development_score": scores.get("development_score"),
        "commercial_score": scores.get("commercial_score"),
        "population_density": demo.get("population_density"),
        "average_income": demo.get("average_income"),
        "city_average_income": city_ctx.get("city_average_income") if isinstance(city_ctx, dict) else None,
    }
    income_relative_to_city = None
    if fields["average_income"] and fields["city_average_income"]:
        income_relative_to_city = round(fields["average_income"] / fields["city_average_income"], 3)

    return {**fields, "locality_income_vs_city_average_income_ratio": income_relative_to_city}


if __name__ == "__main__":
    import json
    import os
    import sys

    sys.path.insert(0, os.path.abspath(""))
    from data_loader import load_locality_geo_from_csv

    geo = load_locality_geo_from_csv(2)  # locality with multiple infra types
    print(
        json.dumps(
            {
                "accessibility": compute_accessibility(geo),
                "infrastructure": compute_infrastructure_intelligence(geo),
                "neighborhood_quality": compute_neighborhood_quality(geo),
            },
            indent=2,
            default=str,
        )
    )
