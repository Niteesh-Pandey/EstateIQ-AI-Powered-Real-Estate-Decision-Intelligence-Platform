"""
Phase 9, Section 9.2 -- Data Agent
======================================
Retrieves validated property facts. Source: PostgreSQL / Phase 1 (§9.2).
Deliberately thin: reads `core.properties` + `core.projects` + `core.localities`
+ `core.cities` directly (same DB/CSV dual-path convention as every other
phase), rather than going through Phase 6's finance-flavored data_loader --
this agent's job is *facts*, not financial assumptions.
"""
import os
import sys

import pandas as pd

_HERE = os.getcwd()
sys.path.insert(0, _HERE)
#_HERE = os.path.dirname(os.path.abspath(__file__))
#sys.path.insert(0, _HERE)
from contracts import AgentFinding

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(_HERE)), "data", "processed")


def _load_csv(name):
    return pd.read_csv(os.path.join(_DATA_DIR, f"{name}.csv"))


def get_property_facts(property_id: int, source: str = "csv") -> AgentFinding:
    if source == "db":
        sys.path.append(os.path.join(os.path.dirname(_HERE), "..", "db"))
        from connection import get_cursor
        with get_cursor() as cur:
            cur.execute("SELECT * FROM core.properties WHERE property_id = %s;", (property_id,))
            prop_rows = cur.fetchall()
            if not prop_rows:
                return _not_found(property_id)
            cur.execute("""
                SELECT pr.project_id, pr.locality_id, pr.developer_id, pr.project_type, pr.project_status,
                       l.locality_name, l.city_id, c.city_name, c.state
                FROM core.projects pr
                JOIN core.localities l ON l.locality_id = pr.locality_id
                JOIN core.cities c ON c.city_id = l.city_id
                WHERE pr.project_id = %s;
            """, (prop_rows[0]["project_id"],))
            ctx_rows = cur.fetchall()
        prop = prop_rows[0]
        ctx = ctx_rows[0] if ctx_rows else {}
    else:
        properties = _load_csv("properties")
        projects = _load_csv("projects")
        localities = _load_csv("localities")
        cities = _load_csv("cities")

        p = properties[properties["property_id"] == property_id]
        if p.empty:
            return _not_found(property_id)
        prop = p.iloc[0].to_dict()

        ctx = {}
        proj = projects[projects["project_id"] == prop["project_id"]]
        if not proj.empty:
            proj = proj.iloc[0]
            ctx.update({"project_id": int(proj["project_id"]), "locality_id": int(proj["locality_id"]),
                        "developer_id": int(proj["developer_id"]), "project_type": proj["project_type"],
                        "project_status": proj["project_status"]})
            loc = localities[localities["locality_id"] == proj["locality_id"]]
            if not loc.empty:
                loc = loc.iloc[0]
                ctx["locality_name"] = loc["locality_name"]
                city = cities[cities["city_id"] == loc["city_id"]]
                if not city.empty:
                    ctx["city_name"] = city.iloc[0]["city_name"]
                    ctx["state"] = city.iloc[0]["state"]

    facts = {
        "property_id": int(prop["property_id"]),
        "property_type": prop.get("property_type"),
        "bedrooms": _n(prop.get("bedrooms")),
        "bathrooms": _n(prop.get("bathrooms")),
        "area_sqft": _n(prop.get("area_sqft")),
        "floor": _n(prop.get("floor")),
        "total_floors": _n(prop.get("total_floors")),
        "age_years": _n(prop.get("age_years")),
        "furnishing": prop.get("furnishing"),
        "asking_price": _n(prop.get("asking_price")),
        "monthly_rent_listed": _n(prop.get("monthly_rent")),
        "locality_id": ctx.get("locality_id"),
        "locality_name": ctx.get("locality_name"),
        "city_name": ctx.get("city_name"),
        "state": ctx.get("state"),
        "developer_id": ctx.get("developer_id"),
        "project_id": ctx.get("project_id"),
        "project_status": ctx.get("project_status"),
    }

    missing_core = [k for k in ("asking_price", "area_sqft", "locality_id") if facts.get(k) is None]
    status = "PASS" if not missing_core else "PASS WITH LIMITATIONS"

    return AgentFinding(
        agent_name="DataAgent", status=status, finding_type="property_facts",
        summary=f"Property {property_id} is a {facts['bedrooms']}BHK {facts['property_type']} in "
                f"{facts.get('locality_name')}, {facts.get('city_name')} "
                f"(₹{facts['asking_price']:,.0f} asking price)." if facts.get("asking_price") else
                f"Property {property_id} facts retrieved with gaps: missing {missing_core}.",
        metrics={"asking_price": facts["asking_price"], "area_sqft": facts["area_sqft"],
                 "monthly_rent_listed": facts["monthly_rent_listed"]},
        source=f"core.properties + core.projects + core.localities + core.cities ({source} path)",
        confidence=100.0 if status == "PASS" else 60.0,
        limitations=[f"Missing core fields: {missing_core}"] if missing_core else [],
        raw=facts,
    )


def _not_found(property_id) -> AgentFinding:
    return AgentFinding(
        agent_name="DataAgent", status="INSUFFICIENT DATA", finding_type="property_facts",
        summary=f"property_id={property_id} was not found in core.properties.",
        source="core.properties", confidence=0.0,
        limitations=["property_id does not exist in the validated Phase 1 dataset."],
        raw=None,
    )


def _n(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    return float(v)


if __name__ == "__main__":
    import json
    print(json.dumps(get_property_facts(1).to_dict(), indent=2, default=str))
