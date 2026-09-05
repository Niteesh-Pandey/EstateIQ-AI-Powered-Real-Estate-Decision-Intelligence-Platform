"""
Phase 7 -- Numbered CSV export, matching the Phase 3/5/6 convention.
"""
import argparse
import os
import sys

import pandas as pd

# Use os.getcwd() in Jupyter Notebooks instead of __file__
try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _HERE = os.getcwd()

sys.path.insert(0, _HERE)
from batch_runner_risk import run_risk_batch
from batch_runner import portfolio_coverage_stats, select_demo_sample # reused from Phase 6
OUT_DIR = os.path.join(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath("")))
    ),
    "docs",
    "risk_results_csv",
)

def build_tables(batch: list):
    summary_rows, dist_rows, driver_rows, stability_rows, scenario_rows = [], [], [], [], []

    for b in batch:
        pid = b["property_id"]
        if b.get("monte_carlo_status") != "OK":
            summary_rows.append({"property_id": pid, "status": "INSUFFICIENT DATA",
                                  "reason": b.get("reason")})
            continue

        risk = b["risk_metrics"]
        stability = b["decision_stability"]
        summary_rows.append({
            "property_id": pid,
            "locality_name": b.get("locality_name"),
            "calibration_status": risk["calibration_status"],
            "n_simulations_valid": risk["n_simulations_valid"],
            "target_irr": risk["target_irr"],
            "irr_mean": risk["irr_distribution"]["mean"],
            "irr_std": risk["irr_distribution"]["std"],
            "npv_mean": risk["npv_distribution"]["mean"],
            "probability_negative_npv": risk["probability_negative_npv"],
            "probability_negative_irr": risk["probability_negative_irr"],
            "probability_meets_target_irr": risk["probability_meets_target_irr"],
            "var_95_npv": risk["var_95_npv"],
            "cvar_95_npv": risk["cvar_95_npv"],
            "base_case_label": stability["base_case_label"],
            "majority_label": stability["majority_label"],
            "stability_pct": stability["stability_pct"],
            "unstable": stability["unstable"],
        })

        dist_rows.append({"property_id": pid, "metric": "irr", **risk["irr_distribution"].get("percentiles", {})})
        dist_rows.append({"property_id": pid, "metric": "npv", **risk["npv_distribution"]["percentiles"]})

        for d in risk["risk_drivers_ranked"]:
            driver_rows.append({"property_id": pid, **d})

        stability_rows.append({"property_id": pid, **stability["decision_distribution_pct"]})

        for row in b["scenario_summary"]:
            scenario_rows.append({"property_id": pid, **row})

    return {
        "01_risk_summary": pd.DataFrame(summary_rows),
        "02_irr_npv_percentiles": pd.DataFrame(dist_rows),
        "03_risk_drivers": pd.DataFrame(driver_rows),
        "04_decision_stability": pd.DataFrame(stability_rows),
        "05_extended_scenario_comparison": pd.DataFrame(scenario_rows),
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["csv", "db"], default="db")
    parser.add_argument("--n", type=int, default=25)
    parser.add_argument("--sims", type=int, default=2000)
    
    # Use parse_known_args instead of parse_args:
    args, _ = parser.parse_known_args()
    
    os.makedirs(OUT_DIR, exist_ok=True)
    coverage = portfolio_coverage_stats()
    pd.DataFrame([coverage]).to_csv(os.path.join(OUT_DIR, "00_portfolio_coverage.csv"), index=False)

    ids = select_demo_sample(args.n, source=args.source)
    batch = run_risk_batch(ids, source=args.source, n_simulations=args.sims)
    tables = build_tables(batch)
    for name, df in tables.items():
        path = os.path.join(OUT_DIR, f"{name}.csv")
        df.to_csv(path, index=False)
        print(f"Wrote {path} ({len(df)} rows)")


if __name__ == "__main__":
    main()
