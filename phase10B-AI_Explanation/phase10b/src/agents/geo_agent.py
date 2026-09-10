"""
Phase 9, Section 9.2 -- Geo Agent
=====================================
"Calls Phase 8." No geo math happens here -- `geo_engine.run_geo_engine()`
is called directly, a byte-identical copy of the Phase 8 file. The
`flood_risk`/`environmental_risk` INSUFFICIENT DATA status (§8.7) is passed
through unmodified -- this agent never fills those in.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "geo"))
from contracts import AgentFinding
from geo_engine import run_geo_engine


def get_geo_analysis(locality_id: int, source: str = "csv") -> AgentFinding:
    if locality_id is None:
        return AgentFinding(
            agent_name="GeoAgent", status="INSUFFICIENT DATA", finding_type="geo_analysis",
            summary="No locality_id available (Data Agent could not resolve one).",
            source="Phase 8 geo_engine", confidence=0.0,
        )

    result = run_geo_engine(locality_id, source=source)

    if result["validation_status"] == "INSUFFICIENT DATA":
        return AgentFinding(
            agent_name="GeoAgent", status="INSUFFICIENT DATA", finding_type="geo_analysis",
            summary=f"No geo data for locality_id={locality_id}: {result.get('reason')}",
            source="Phase 8 geo_engine.run_geo_engine (unchanged)", confidence=0.0,
        )

    ls = result["location_score"]
    gr = result["geo_risk"]
    summary = (f"{result['locality_name']}, {result['city']}: location score "
               f"{ls['location_score']:.1f}/100, accessibility score "
               f"{result['accessibility']['accessibility_score'] or 0:.1f}/100. "
               f"Flood/environmental risk: {gr['flood_risk']['status']} (no such data exists).")

    status = "PASS" if result["validation_status"] == "PASS" else "PASS WITH LIMITATIONS"
    confidence = 85.0 if status == "PASS" else 55.0

    return AgentFinding(
        agent_name="GeoAgent", status=status, finding_type="geo_analysis",
        summary=summary,
        metrics={
            "location_score": ls["location_score"],
            "accessibility_score": result["accessibility"]["accessibility_score"],
            "infrastructure_delivery_risk": gr["infrastructure_delivery_risk"].get("score_0_100"),
            "infrastructure_concentration_risk": gr["infrastructure_concentration_risk"].get("score_0_100"),
            "flood_risk_status": gr["flood_risk"]["status"],
            "environmental_risk_status": gr["environmental_risk"]["status"],
        },
        source="Phase 8 geo_engine.run_geo_engine (unchanged)",
        confidence=confidence,
        limitations=result.get("limitations", []),
        raw=result,
    )


if __name__ == "__main__":
    print(get_geo_analysis(2).to_dict())
