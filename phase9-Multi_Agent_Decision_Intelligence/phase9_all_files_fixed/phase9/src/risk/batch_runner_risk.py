"""
Phase 7 -- Batch runner used by the report/CSV/chart orchestrators.
Reuses Phase 6's `batch_runner.select_demo_sample` unchanged (same
eligibility bar: OBSERVED expense + rental history + reliable locality
appreciation), so the same 25 properties can be compared across Phase 6's
deterministic results and Phase 7's simulated risk results.
"""
import argparse
import os
import sys

_HERE = os.getcwd()
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "finance"))
sys.path.insert(0, _HERE)

import os

# Set database environment variables
os.environ["DB_USER"] = "postgres"  # Replace 'postgres' if your database username is different
os.environ["DB_PASSWORD"] = "admin123"
os.environ["DB_NAME"] = "real_estate_db"
os.environ["DB_HOST"] = "localhost"  # Default host
os.environ["DB_PORT"] = "5432"  # Default PostgreSQL port

from data_loader import load_property_financials_from_csv, load_property_financials_from_db
from engine import FinancialAssumptions
from batch_runner import portfolio_coverage_stats, select_demo_sample  # noqa: reused from Phase 6
from monte_carlo import run_monte_carlo, MonteCarloConfig
from risk_metrics import compute_risk_metrics
from decision_stability import compute_decision_stability
from scenario_engine import run_extended_scenarios, extended_scenario_summary


def run_risk_batch(property_ids: list, source: str = "csv", n_simulations: int = 2000, seed: int = 42) -> list:
    loader = load_property_financials_from_csv if source == "csv" else load_property_financials_from_db
    batch = []
    for pid in property_ids:
        observed = loader(pid)
        if observed.get("status") != "OK":
            batch.append({"property_id": pid, "status": "INSUFFICIENT DATA", "reason": observed.get("reason")})
            continue

        assumptions = FinancialAssumptions(property_id=pid)  # resolved entirely from OBSERVED data,
        # same convention as Phase 6's demo batch -- keeps OBSERVED/ASSUMED boundary auditable.
        mc = run_monte_carlo(assumptions, observed, MonteCarloConfig(n_simulations=n_simulations, seed=seed))
        risk = compute_risk_metrics(mc)
        stability = compute_decision_stability(mc)
        scenarios = run_extended_scenarios(assumptions, observed)

        batch.append({
            "property_id": pid,
            "locality_name": observed.get("locality_name"),
            "monte_carlo_status": mc.get("status"),
            "risk_metrics": risk,
            "decision_stability": stability,
            "scenario_summary": extended_scenario_summary(scenarios),
        })
    return batch


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["csv", "db"], default="db")
    parser.add_argument("--n", type=int, default=25)
    parser.add_argument("--sims", type=int, default=2000)
    #args = parser.parse_args()
    args, _ = parser.parse_known_args()
    
    print("Coverage:", portfolio_coverage_stats())
    ids = select_demo_sample(args.n, source=args.source)
    print(f"Selected {len(ids)} demo property_ids: {ids[:10]}...")
    batch = run_risk_batch(ids, source=args.source, n_simulations=args.sims)
    ok = sum(1 for b in batch if b.get("monte_carlo_status") == "OK")
    print(f"Monte Carlo OK: {ok}/{len(batch)}")
