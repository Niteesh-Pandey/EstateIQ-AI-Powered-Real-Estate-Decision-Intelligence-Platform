"""
Phase 8 -- Numbered CSV export, matching the Phase 3/5/6/7 convention.
Runs across all 90 localities (full portfolio, not a sample).
"""
import argparse
import os
import sys

import pandas as pd

_HERE = os.getcwd()
#_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from batch_runner import run_full_batch

# Replaced __file__ with _HERE
OUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(_HERE))),
    "docs",
    "geo_results_csv"
)
#OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    #os.path.abspath(__file__)))), "docs", "geo_results_csv")


def build_tables(batch: list):
    summary_rows, infra_rows, risk_rows, score_rows = [], [], [], []

    for r in batch:
        lid = r["locality_id"]
        if r["validation_status"] == "INSUFFICIENT DATA":
            summary_rows.append({"locality_id": lid, "status": "INSUFFICIENT DATA", "reason": r.get("reason")})
            continue

        summary_rows.append({
            "locality_id": lid,
            "locality_name": r["locality_name"],
            "city": r["city"],
            "state": r["state"],
            "latitude": r["coordinates"]["latitude"],
            "longitude": r["coordinates"]["longitude"],
            "validation_status": r["validation_status"],
            "location_score": r["location_score"]["location_score"],
            "accessibility_score": r["accessibility"]["accessibility_score"],
        })

        infra = r["infrastructure"]
        infra_rows.append({
            "locality_id": lid,
            "total_items": infra["total_infrastructure_items"],
            "n_planned": infra["n_planned"],
            "n_completed": infra["n_completed"],
            "social_score": infra["social_infrastructure"]["score"],
            "transit_score": infra["transit_infrastructure"]["score"],
            "commercial_score": infra["commercial_infrastructure"]["score"],
        })

        gr = r["geo_risk"]
        risk_rows.append({
            "locality_id": lid,
            "flood_risk_status": gr["flood_risk"]["status"],
            "environmental_risk_status": gr["environmental_risk"]["status"],
            "infrastructure_delivery_risk_score": gr["infrastructure_delivery_risk"].get("score_0_100"),
            "infrastructure_concentration_risk_score": gr["infrastructure_concentration_risk"].get("score_0_100"),
        })

        ls = r["location_score"]
        score_rows.append({"locality_id": lid, "status": ls["status"],
                            "location_score": ls["location_score"], **(ls.get("components_used") or {})})

    return {
        "01_locality_summary": pd.DataFrame(summary_rows),
        "02_infrastructure_intelligence": pd.DataFrame(infra_rows),
        "03_geo_risk": pd.DataFrame(risk_rows),
        "04_location_score_breakdown": pd.DataFrame(score_rows),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["csv", "db"], default="db")
    args, _ = parser.parse_known_args()  # Ignores Jupyter's internal -f kernel flag
    os.makedirs(OUT_DIR, exist_ok=True)
    batch = run_full_batch(source=args.source)
    tables = build_tables(batch)
    for name, df in tables.items():
        path = os.path.join(OUT_DIR, f"{name}.csv")
        df.to_csv(path, index=False)
        print(f"Wrote {path} ({len(df)} rows)")

if __name__ == "__main__":
    main()
