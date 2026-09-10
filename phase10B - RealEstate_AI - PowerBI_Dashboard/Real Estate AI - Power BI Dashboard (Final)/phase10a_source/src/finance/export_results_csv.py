"""
Phase 6 -- Numbered CSV export, matching Phase 3/5's `docs/*_results_csv/`
convention. Defaults to the production DB path; `--source csv` is the
documented dev/test-only path (see data_loader.py docstring).
"""
import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from batch_runner import portfolio_coverage_stats, select_demo_sample, run_batch

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "docs", "financial_results_csv")


def build_tables(batch: list):
    property_rows, cashflow_rows, metric_rows, scenario_rows, sensitivity_rows = [], [], [], [], []

    for b in batch:
        pid = b["property_id"]
        if "observed" not in b:
            property_rows.append({"property_id": pid, "status": "INSUFFICIENT DATA",
                                   "reason": b.get("reason")})
            continue

        base = b["scenarios"]["Base"]
        property_rows.append({
            "property_id": pid,
            "locality_name": b.get("locality_name"),
            "asking_price": b["observed"]["property_facts"]["asking_price"],
            "monthly_rent_listed": b["observed"]["property_facts"]["monthly_rent_listed"],
            "expense_records_used": b["observed"]["expense_records_used"],
            "rental_records_used": b["observed"]["rental_records_used"],
            "observed_vacancy_rate": b["observed"]["observed_vacancy_rate"],
            "observed_locality_appreciation": b["observed"]["observed_locality_appreciation"]
                .get("annualized_growth_rate"),
            "base_validation_status": base["validation_status"],
        })

        if base.get("cash_flows"):
            cf = base["cash_flows"]
            cashflow_rows.append({"property_id": pid, **cf, "cash_flow_schedule": str(cf["cash_flow_schedule"])})
        if base.get("metrics"):
            metric_rows.append({"property_id": pid, **base["metrics"]})

        for row in b["scenario_summary"]:
            scenario_rows.append({"property_id": pid, **row})

        sens = b.get("sensitivity", {})
        for driver, block in sens.items():
            if block.get("status") != "OK":
                continue
            for r in block["rows"]:
                sensitivity_rows.append({"property_id": pid, "driver": driver, **r})

    return {
        "01_property_financial_summary": pd.DataFrame(property_rows),
        "02_cash_flow_detail": pd.DataFrame(cashflow_rows),
        "03_financial_metrics": pd.DataFrame(metric_rows),
        "04_scenario_comparison": pd.DataFrame(scenario_rows),
        "05_sensitivity_analysis": pd.DataFrame(sensitivity_rows),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["csv", "db"], default="db")
    parser.add_argument("--n", type=int, default=25)
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    coverage = portfolio_coverage_stats()
    pd.DataFrame([coverage]).to_csv(os.path.join(OUT_DIR, "00_portfolio_coverage.csv"), index=False)

    ids = select_demo_sample(args.n, source=args.source)
    batch = run_batch(ids, source=args.source)
    tables = build_tables(batch)
    for name, df in tables.items():
        path = os.path.join(OUT_DIR, f"{name}.csv")
        df.to_csv(path, index=False)
        print(f"Wrote {path} ({len(df)} rows)")


if __name__ == "__main__":
    main()
