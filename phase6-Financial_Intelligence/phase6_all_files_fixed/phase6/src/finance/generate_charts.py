#!/usr/bin/env python
# coding: utf-8

# In[4]:


"""
Phase 6 -- Chart Generator
Matches Phase 3/5's docs/*_charts/ convention.
"""
import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

# Database Connection Credentials
os.environ["DB_USER"] = "postgres"           
os.environ["DB_PASSWORD"] = "admin123"
os.environ["DB_NAME"] = "real_estate_db"
os.environ["DB_HOST"] = "localhost"
os.environ["DB_PORT"] = "5432"


current_dir = os.getcwd()
sys.path.insert(0, current_dir)
OUT_DIR = os.path.join(current_dir, "..", "..", "docs", "finance_charts")

from batch_runner import select_demo_sample, run_batch


def main(source="db", n=25):
    os.makedirs(OUT_DIR, exist_ok=True)
    ids = select_demo_sample(n, source=source)
    batch = run_batch(ids, source=source)

    metrics_rows = [{"property_id": b["property_id"], **b["scenarios"]["Base"]["metrics"]}
                     for b in batch if b["scenarios"]["Base"].get("metrics")]
    df = pd.DataFrame(metrics_rows)

    # Chart 1: IRR distribution across the demo batch (Base scenario)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.hist(df["irr"].dropna() * 100, bins=12, color="#2c3e50", edgecolor="white")
    ax.set_title("Base-Scenario IRR Distribution (demo batch, n=%d)" % len(df))
    ax.set_xlabel("IRR (%)")
    ax.set_ylabel("Number of properties")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "irr_distribution.png"), dpi=140)
    plt.close(fig)

    # Chart 2: scenario comparison (mean IRR by scenario)
    scen_rows = []
    for b in batch:
        for row in b["scenario_summary"]:
            scen_rows.append(row)
    scen_df = pd.DataFrame(scen_rows)
    scen_df = scen_df[scen_df["validation_status"] == "PASS"]
    means = scen_df.groupby("scenario")["irr"].mean().reindex(["Downside", "Base", "Upside"])
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    colors = ["#c0392b", "#2c3e50", "#27ae60"]
    ax.bar(means.index, means.values * 100, color=colors)
    ax.set_title("Mean IRR by Scenario (demo batch)")
    ax.set_ylabel("IRR (%)")
    ax.axhline(0, color="black", linewidth=0.8)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "scenario_mean_irr.png"), dpi=140)
    plt.close(fig)

    # Chart 3: cap rate vs cash-on-cash scatter
    fig, ax = plt.subplots(figsize=(6.5, 5))
    ax.scatter(df["cap_rate"] * 100, df["cash_on_cash_return"] * 100, color="#2c3e50", alpha=0.75)
    ax.set_xlabel("Cap Rate (%)")
    ax.set_ylabel("Cash-on-Cash Return (%)")
    ax.set_title("Cap Rate vs. Cash-on-Cash Return (demo batch)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "cap_rate_vs_coc.png"), dpi=140)
    plt.close(fig)

    # Chart 4: sensitivity tornado for one representative property
    rep = batch[0]
    sens = rep["sensitivity"]
    tornado_rows = []
    for driver, block in sens.items():
        if block.get("status") != "OK":
            continue
        irrs = [r["irr"] for r in block["rows"] if r["irr"] is not None]
        if irrs:
            tornado_rows.append((driver, max(irrs) - min(irrs)))
    tornado_rows.sort(key=lambda x: x[1])
    fig, ax = plt.subplots(figsize=(7, 4.5))
    labels = [t[0] for t in tornado_rows]
    spans = [t[1] * 100 for t in tornado_rows]
    ax.barh(labels, spans, color="#2c3e50")
    ax.set_title(f"IRR Sensitivity Range by Driver -- Property {rep['property_id']}")
    ax.set_xlabel("IRR range across tested driver values (percentage points)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "sensitivity_tornado_example.png"), dpi=140)
    plt.close(fig)

    print(f"Wrote 4 charts to {OUT_DIR}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["csv", "db"], default="db")
    parser.add_argument("--n", type=int, default=25)
    
    # Pass [] so argparse ignores Jupyter's command line flags
    args = parser.parse_args([])
    
    main(source=args.source, n=args.n)
"""if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["csv", "db"], default="db")
    parser.add_argument("--n", type=int, default=25)
    args = parser.parse_args()
    main(source=args.source, n=args.n)
"""


# In[ ]:



