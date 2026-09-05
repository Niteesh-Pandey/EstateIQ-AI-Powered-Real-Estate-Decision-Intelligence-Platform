


"""
Phase 6 -- Batch runner used by the report/CSV/chart orchestrators.
Selects a demo sample of properties that actually have OBSERVED expense +
rental history + a reliable locality appreciation signal (so the batch
demonstrates PASS results, not a wall of INSUFFICIENT DATA), and clearly
reports what fraction of the full portfolio meets that bar.
"""
import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.getcwd())\

from data_loader import (load_property_financials_from_csv,
                          load_property_financials_from_db, _locality_appreciation)
from engine import FinancialAssumptions, run_financial_engine
from scenarios import run_scenarios, scenario_summary, run_sensitivity

#_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    
_DATA_DIR = r"C:\Users\Admin\Downloads\phase6_all_files_fixed\phase6\data\processed"    

def portfolio_coverage_stats() -> dict:
    props = pd.read_csv(os.path.join(_DATA_DIR, "properties.csv"))
    exp = pd.read_csv(os.path.join(_DATA_DIR, "expenses.csv"))
    rent = pd.read_csv(os.path.join(_DATA_DIR, "rentals.csv"))
    with_exp = exp["property_id"].nunique()
    with_rent = rent["property_id"].nunique()
    with_both = len(set(exp["property_id"]) & set(rent["property_id"]))
    return {
        "total_properties": int(len(props)),
        "with_expense_history": int(with_exp),
        "with_rental_history": int(with_rent),
        "with_both": int(with_both),
        "pct_with_both": round(100 * with_both / len(props), 1),
    }


def select_demo_sample(n: int = 25, seed: int = 42, source: str = "csv") -> list:
    """Picks properties that have BOTH expense and rental history AND a
    reliable locality appreciation signal, so the demo batch is
    representative of a resolvable deal, not dominated by data gaps.
    Sampling is deterministic (fixed seed) for reproducibility."""
    exp = pd.read_csv(os.path.join(_DATA_DIR, "expenses.csv"))
    rent = pd.read_csv(os.path.join(_DATA_DIR, "rentals.csv"))
    props = pd.read_csv(os.path.join(_DATA_DIR, "properties.csv"))
    projects = pd.read_csv(os.path.join(_DATA_DIR, "projects.csv"))
    market = pd.read_csv(os.path.join(_DATA_DIR, "market_monthly.csv"))

    candidates = sorted(set(exp["property_id"]) & set(rent["property_id"]) & set(props["property_id"]))

    reliable_localities = set()
    for lid in market["locality_id"].unique():
        r = _locality_appreciation(market, lid)
        if r.get("reliable_for_use_as_default"):
            reliable_localities.add(lid)

    prop_to_locality = props.merge(projects[["project_id", "locality_id"]], on="project_id", how="left") \
        .set_index("property_id")["locality_id"].to_dict()

    filtered = [pid for pid in candidates if prop_to_locality.get(pid) in reliable_localities]

    import random
    rng = random.Random(seed)
    rng.shuffle(filtered)
    return filtered[:n]


def run_batch(property_ids: list, source: str = "csv") -> list:
    loader = load_property_financials_from_csv if source == "csv" else load_property_financials_from_db
    batch = []
    for pid in property_ids:
        observed = loader(pid)
        if observed.get("status") != "OK":
            batch.append({"property_id": pid, "validation_status": "INSUFFICIENT DATA",
                          "reason": observed.get("reason")})
            continue
        assumptions = FinancialAssumptions(property_id=pid)  # deliberately no overrides:
        # forces the engine to resolve everything from OBSERVED data, which is the point
        # of this demo batch (only OBSERVED-resolvable properties were selected).
        scen = run_scenarios(assumptions, observed)
        sens = run_sensitivity(assumptions, observed)
        batch.append({
            "property_id": pid,
            "locality_name": observed.get("locality_name"),
            "observed": observed,
            "scenarios": scen,
            "scenario_summary": scenario_summary(scen),
            "sensitivity": sens,
        })
    return batch


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["csv", "db"], default="db")
    parser.add_argument("--n", type=int, default=25)


    args, unknown = parser.parse_known_args(["--source", "csv"])
    print("Coverage:", portfolio_coverage_stats())
    ids = select_demo_sample(args.n, source=args.source)
    print(f"Selected {len(ids)} demo property_ids: {ids[:10]}...")
    batch = run_batch(ids, source=args.source)
    passed = sum(1 for b in batch if b.get("scenario_summary") and
                 b["scenario_summary"][1]["validation_status"] == "PASS")
    print(f"Base scenario PASS: {passed}/{len(batch)}")


# In[ ]:



