"""
Phase 8, Section 8.7 -- Geo Risk
====================================
Master Prompt Section 8.7 is explicit: "Never invent geo-risk values."

This dataset contains no flood, environmental, or climate/hazard data of
any kind (no elevation, no floodplain maps, no environmental monitoring
data anywhere in Phase 1). `flood_risk` and `environmental_risk` are
therefore hard-coded to `INSUFFICIENT DATA` -- not estimated from proxies
like elevation or coastal distance, because this platform has no such
inputs to estimate from either.

Two risk dimensions ARE computable from real data, and are computed here as
explicitly-labeled PROXY indicators (not calibrated real-world
probabilities, matching the honesty standard Phase 7 set for Monte Carlo):

  infrastructure_delivery_risk -- what share of a locality's infrastructure
  "story" (by impact_score) is still planned rather than completed. A
  locality whose infrastructure_score is heavily supported by not-yet-built
  projects carries more execution risk than one already built out.

  infrastructure_concentration_risk -- a Herfindahl-Hirschman-style
  concentration index over a locality's infrastructure impact scores. A
  locality whose access story rests on one or two dominant items (e.g. a
  single highway) is more exposed to a single point of failure than one
  with many comparable contributors.
"""
import numpy as np


def compute_geo_risk(geo_record: dict) -> dict:
    inventory = geo_record.get("infrastructure_inventory", {})
    items = inventory.get("items", [])

    result = {
        "flood_risk": {"status": "INSUFFICIENT DATA",
                        "reason": "No flood/hazard data exists anywhere in this platform's data sources."},
        "environmental_risk": {"status": "INSUFFICIENT DATA",
                                "reason": "No environmental/climate monitoring data exists in this platform's "
                                          "data sources."},
        "infrastructure_delivery_risk": _delivery_risk(items),
        "infrastructure_concentration_risk": _concentration_risk(items),
    }
    return result


def _delivery_risk(items: list) -> dict:
    if not items:
        return {"status": "INSUFFICIENT DATA", "score": None}
    total_impact = sum(i["impact_score"] for i in items)
    if total_impact <= 0:
        return {"status": "INSUFFICIENT DATA", "score": None}
    planned_impact = sum(i["impact_score"] for i in items if i["is_planned"])
    pct_planned = planned_impact / total_impact
    return {
        "status": "PROXY_INDICATOR",
        "pct_of_infrastructure_impact_still_planned": round(pct_planned, 3),
        "score_0_100": round(pct_planned * 100, 1),
        "interpretation": "Higher = more of this locality's infrastructure story depends on projects not "
                           "yet completed; not a calibrated probability that any specific project slips.",
    }


def _concentration_risk(items: list) -> dict:
    if len(items) == 0:
        return {"status": "INSUFFICIENT DATA", "score": None}
    impacts = np.array([i["impact_score"] for i in items], dtype=float)
    total = impacts.sum()
    if total <= 0:
        return {"status": "INSUFFICIENT DATA", "score": None}
    shares = impacts / total
    hhi = float(np.sum(shares ** 2)) * 10000  # standard HHI scale, 0 (max diversity) to 10000 (single item)
    # Normalize to 0-100 for consistency with other GeoResult scores.
    # Floor HHI for n items is 10000/n (perfectly even split); 10000 is the
    # single-item ceiling. Scale so "as concentrated as possible given n" ~ mid-range,
    # not artificially near 0, since a locality with few infra records is
    # structurally more concentrated regardless of how evenly those few are spread.
    hhi_floor = 10000 / len(items)
    normalized = 100 * (hhi - hhi_floor) / (10000 - hhi_floor) if len(items) > 1 else 100.0
    return {
        "status": "PROXY_INDICATOR",
        "hhi": round(hhi, 1),
        "n_items": len(items),
        "score_0_100": round(max(0.0, min(100.0, normalized)), 1),
        "interpretation": "Higher = this locality's infrastructure access depends more heavily on a small "
                           "number of dominant items (single-point-of-failure exposure); not a calibrated "
                           "probability of any specific loss event.",
    }


if __name__ == "__main__":
    import json
    import os
    import sys

    sys.path.insert(0, os.getcwd())
    #sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from data_loader import load_locality_geo_from_csv

    geo = load_locality_geo_from_csv(1)  # single-item locality -> should show max concentration
    print(json.dumps(compute_geo_risk(geo), indent=2, default=str))
