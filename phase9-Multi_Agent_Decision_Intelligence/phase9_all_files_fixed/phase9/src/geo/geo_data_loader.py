"""at this dataset does NOT have, and this module therefore never invents
(Section 8.7 -- "Never invent geo-risk values"): flood risk, environmental
risk, or any climate/hazard indicator. Any downstream component asking for
those returns INSUFFICIENT DATA, not a fabricated number.
"""
import os
import sys

import pandas as pd

# Use os.getcwd() instead of __file__ in Jupyter Notebooks
_HERE = os.getcwd()
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(_HERE)), "data", "processed")

TODAY = pd.Timestamp("2026-09-03")


def _csv(name: str) -> pd.DataFrame:
    return pd.read_csv(os.path.join(_DATA_DIR, f"{name}.csv"))


def load_locality_geo_from_csv(locality_id: int) -> dict:
    localities = _csv("localities")
    cities = _csv("cities")
    infrastructure = _csv("infrastructure")
    market_monthly = _csv("market_monthly")
    return _assemble(locality_id, localities, cities, infrastructure, market_monthly)


def load_locality_geo_from_db(locality_id: int) -> dict:
    """PRODUCTION PATH. Queries core.* on the live PostgreSQL database."""
    sys.path.append(os.path.join(os.path.dirname(_HERE), "..", "db"))
    from connection import get_cursor  # noqa: E402

    with get_cursor() as cur:
        cur.execute("SELECT * FROM core.localities WHERE locality_id = %s;", (locality_id,))
        loc_rows = cur.fetchall()
        if not loc_rows:
            return {"locality_id": locality_id, "status": "INSUFFICIENT DATA",
                    "reason": "locality_id not found in core.localities"}
        cur.execute("SELECT * FROM core.cities WHERE city_id = %s;", (loc_rows[0]["city_id"],))
        city_rows = cur.fetchall()
        cur.execute("SELECT * FROM core.infrastructure WHERE locality_id = %s;", (locality_id,))
        infra_rows = cur.fetchall()
        cur.execute("SELECT * FROM core.market_monthly WHERE locality_id = %s ORDER BY month;", (locality_id,))
        mkt_rows = cur.fetchall()

    localities = pd.DataFrame(loc_rows)
    cities = pd.DataFrame(city_rows)
    infrastructure = pd.DataFrame(infra_rows)
    market_monthly = pd.DataFrame(mkt_rows)
    return _assemble(locality_id, localities, cities, infrastructure, market_monthly)


def _assemble(locality_id, localities, cities, infrastructure, market_monthly) -> dict:
    loc = localities[localities["locality_id"] == locality_id]
    if loc.empty:
        return {"locality_id": locality_id, "status": "INSUFFICIENT DATA",
                "reason": "locality_id not found in core.localities"}
    loc = loc.iloc[0]

    city = None
    if not cities.empty:
        c = cities[cities["city_id"] == loc["city_id"]]
        if not c.empty:
            city = c.iloc[0].to_dict()

    result = {
        "locality_id": int(locality_id),
        "status": "OK",
        "locality_name": loc["locality_name"],
        "city": city.get("city_name") if city else None,
        "state": city.get("state") if city else None,
        "coordinates": {"latitude": float(loc["latitude"]), "longitude": float(loc["longitude"])},
        "observed_scores": {
            # All OBSERVED -- pre-computed feature scores from Phase 1's core.localities,
            # 0-100 scale each. This module does not re-derive them; it consumes them
            # exactly as validated in Phase 1.
            "connectivity_score": _num(loc.get("connectivity_score")),
            "safety_score": _num(loc.get("safety_score")),
            "infrastructure_score": _num(loc.get("infrastructure_score")),
            "development_score": _num(loc.get("development_score")),
            "commercial_score": _num(loc.get("commercial_score")),
        },
        "demographics": {
            "population_density": _num(loc.get("population_density")),
            "average_income": _num(loc.get("average_income")),
        },
        "city_context": {
            "population": _num(city.get("population")) if city else None,
            "city_average_income": _num(city.get("average_income")) if city else None,
            "city_development_score": _num(city.get("development_score")) if city else None,
        } if city else {"status": "INSUFFICIENT DATA"},
        "governance": {k: "OBSERVED" for k in
                       ["connectivity_score", "safety_score", "infrastructure_score",
                        "development_score", "commercial_score", "population_density",
                        "average_income"]},
    }

    # --- Infrastructure inventory (OBSERVED, this locality's own records)
    l_infra = infrastructure[infrastructure["locality_id"] == locality_id] if not infrastructure.empty \
        else pd.DataFrame()
    if not l_infra.empty:
        l_infra = l_infra.copy()
        l_infra["expected_completion"] = pd.to_datetime(l_infra["expected_completion"])
        l_infra["is_planned"] = l_infra["expected_completion"] > TODAY
        by_type = l_infra.groupby("type").agg(
            count=("infrastructure_id", "count"),
            mean_impact_score=("impact_score", "mean"),
            mean_distance_km=("distance_from_center", "mean"),
        ).round(2).to_dict("index")
        result["infrastructure_inventory"] = {
            "total_items": int(len(l_infra)),
            "n_planned": int(l_infra["is_planned"].sum()),
            "n_completed": int((~l_infra["is_planned"]).sum()),
            "by_type": by_type,
            "items": l_infra[["infrastructure_id", "type", "distance_from_center",
                               "expected_completion", "impact_score", "is_planned"]]
                     .sort_values("distance_from_center").to_dict("records"),
        }
    else:
        result["infrastructure_inventory"] = {"total_items": 0, "n_planned": 0, "n_completed": 0,
                                                "by_type": {}, "items": []}

    # --- Market intelligence for this locality (OBSERVED, from market_monthly)
    result["market_intelligence"] = _market_intelligence(market_monthly, locality_id)

    return result


def _market_intelligence(market_monthly: pd.DataFrame, locality_id) -> dict:
    if market_monthly is None or market_monthly.empty:
        return {"status": "INSUFFICIENT DATA"}
    m = market_monthly[market_monthly["locality_id"] == locality_id].copy()
    if m.empty:
        return {"status": "INSUFFICIENT DATA"}
    m["month"] = pd.to_datetime(m["month"])
    m = m.sort_values("month")
    latest = m.iloc[-1]
    recent_12 = m.tail(12)
    return {
        "status": "OBSERVED",
        "latest_month": str(latest["month"].date()),
        "latest_demand_index": _num(latest.get("demand_index")),
        "latest_supply_index": _num(latest.get("supply_index")),
        "latest_absorption_rate": _num(latest.get("absorption_rate")),
        "latest_avg_days_on_market": _num(latest.get("average_days_on_market")),
        "mean_demand_index_last_12m": round(float(recent_12["demand_index"].mean()), 2)
            if "demand_index" in recent_12 else None,
        "mean_supply_index_last_12m": round(float(recent_12["supply_index"].mean()), 2)
            if "supply_index" in recent_12 else None,
        "total_units_sold_last_12m": int(recent_12["units_sold"].sum()) if "units_sold" in recent_12 else None,
        "n_months_observed": int(len(m)),
    }


def _num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    return float(v)


if __name__ == "__main__":
    import json
    print(json.dumps(load_locality_geo_from_csv(1), indent=2, default=str))
