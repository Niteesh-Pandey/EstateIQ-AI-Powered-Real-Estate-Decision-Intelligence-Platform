"""
Phase 7 -- Chart Generator, matching Phase 3/5/6's docs/*_charts/ convention.
"""
import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _HERE = os.getcwd()

sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "finance"))

OUT_DIR = os.path.abspath(os.path.join(_HERE, "..", "..", "docs", "risk_charts"))
from data_loader import load_property_financials_from_csv, load_property_financials_from_db
from engine import FinancialAssumptions
from monte_carlo import run_monte_carlo, MonteCarloConfig
from risk_metrics import compute_risk_metrics
from batch_runner_risk import run_risk_batch
from batch_runner import select_demo_sample


def main(source="db", n=25, sims=2000):
    os.makedirs(OUT_DIR, exist_ok=True)
    ids = select_demo_sample(n, source=source)
    batch = run_risk_batch(ids, source=source, n_simulations=sims)

    # Chart 1: IRR distribution histogram for one representative property (property_id[0])
    loader = load_property_financials_from_csv if source == "csv" else load_property_financials_from_db
    rep_id = ids[0]
    observed = loader(rep_id)
    assumptions = FinancialAssumptions(property_id=rep_id)
    mc = run_monte_carlo(assumptions, observed, MonteCarloConfig(n_simulations=sims, seed=42))
    irrs = np.array([r["irr"] for r in mc["records"] if r["irr"] is not None]) * 100

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.hist(irrs, bins=30, color="#2c3e50", edgecolor="white")
    ax.axvline(np.percentile(irrs, 5), color="#c0392b", linestyle="--", label="P5 (downside)")
    ax.axvline(np.median(irrs), color="#27ae60", linestyle="--", label="Median")
    ax.set_title(f"Monte Carlo IRR Distribution -- Property {rep_id} (n={sims:,} draws)")
    ax.set_xlabel("IRR (%)")
    ax.set_ylabel("Frequency")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "irr_distribution_example.png"), dpi=140)
    plt.close(fig)

    # Chart 2: NPV distribution with VaR/CVaR markers, same property
    risk = compute_risk_metrics(mc)
    npvs = np.array([r["npv"] for r in mc["records"]]) / 1e6
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.hist(npvs, bins=30, color="#34495e", edgecolor="white")
    ax.axvline(risk["var_95_npv"] / 1e6, color="#c0392b", linestyle="--", label="VaR 95%")
    ax.axvline(risk["cvar_95_npv"] / 1e6, color="#8e44ad", linestyle=":", label="CVaR 95%")
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_title(f"Monte Carlo NPV Distribution -- Property {rep_id}")
    ax.set_xlabel("NPV (₹ millions)")
    ax.set_ylabel("Frequency")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "npv_var_cvar_example.png"), dpi=140)
    plt.close(fig)

    # Chart 3: risk driver correlation, averaged across the demo batch
    driver_rows = []
    for b in batch:
        if b.get("risk_metrics", {}).get("status") == "OK":
            for d in b["risk_metrics"]["risk_drivers_ranked"]:
                driver_rows.append(d)
    ddf = pd.DataFrame(driver_rows)
    means = ddf.groupby("driver")["correlation_with_irr"].mean().sort_values()
    fig, ax = plt.subplots(figsize=(7, 4.5))
    colors = ["#c0392b" if v < 0 else "#27ae60" for v in means.values]
    ax.barh(means.index, means.values, color=colors)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_title("Mean IRR Risk-Driver Correlation Across Demo Batch (n=%d)" % len(batch))
    ax.set_xlabel("Pearson correlation with simulated IRR")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "risk_drivers_portfolio.png"), dpi=140)
    plt.close(fig)

    # Chart 4: decision stability distribution across the demo batch
    stab_rows = [{"property_id": b["property_id"], **b["decision_stability"]["decision_distribution_pct"]}
                 for b in batch if b.get("decision_stability", {}).get("status") == "OK"]
    sdf = pd.DataFrame(stab_rows).set_index("property_id")
    sdf = sdf.sort_values("INVEST" if "INVEST" in sdf else sdf.columns[0])
    fig, ax = plt.subplots(figsize=(8, 6))
    bottom = np.zeros(len(sdf))
    colors_map = {"AVOID": "#c0392b", "HOLD": "#f39c12", "INVEST": "#27ae60", "INSUFFICIENT": "#95a5a6"}
    for col in ["AVOID", "HOLD", "INVEST", "INSUFFICIENT"]:
        if col in sdf.columns:
            ax.bar(sdf.index.astype(str), sdf[col], bottom=bottom, label=col, color=colors_map[col])
            bottom += sdf[col].values
    ax.set_title("Decision Label Distribution Under Simulation (demo batch)")
    ax.set_xlabel("Property ID")
    ax.set_ylabel("% of simulated draws")
    ax.legend()
    ax.tick_params(axis="x", rotation=90, labelsize=6)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "decision_stability_portfolio.png"), dpi=140)
    plt.close(fig)

    print(f"Wrote 4 charts to {OUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["csv", "db"], default="db")
    parser.add_argument("--n", type=int, default=25)
    parser.add_argument("--sims", type=int, default=2000)
    
    # Use parse_known_args() so Jupyter's kernel flags (-f ...) are safely ignored:
    args, _ = parser.parse_known_args()
    
    main(source=args.source, n=args.n, sims=args.sims)