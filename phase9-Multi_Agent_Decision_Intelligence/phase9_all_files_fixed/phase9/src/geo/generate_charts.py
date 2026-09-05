"""
Phase 8 -- Chart Generator, matching Phase 3/5/6/7's docs/*_charts/ convention.
"""
import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

_HERE = os.path.abspath(".")
#_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
OUT_DIR = os.path.join(_HERE, "..", "..", "docs", "geo_charts")

from batch_runner import run_full_batch


def main(source="db"):
    os.makedirs(OUT_DIR, exist_ok=True)
    batch = run_full_batch(source=source)
    ok = [b for b in batch if b["validation_status"] != "INSUFFICIENT DATA"]

    df = pd.DataFrame([{
        "locality_name": b["locality_name"], "city": b["city"],
        "location_score": b["location_score"]["location_score"],
        "accessibility_score": b["accessibility"]["accessibility_score"],
        "delivery_risk": b["geo_risk"]["infrastructure_delivery_risk"].get("score_0_100"),
        "concentration_risk": b["geo_risk"]["infrastructure_concentration_risk"].get("score_0_100"),
    } for b in ok])

    # Chart 1: location score distribution
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.hist(df["location_score"].dropna(), bins=15, color="#2c3e50", edgecolor="white")
    ax.set_title(f"Location Score Distribution (n={len(df)} localities)")
    ax.set_xlabel("Location Score (0-100)")
    ax.set_ylabel("Number of localities")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "location_score_distribution.png"), dpi=140)
    plt.close(fig)

    # Chart 2: mean location score by city
    means = df.groupby("city")["location_score"].mean().sort_values()
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.barh(means.index, means.values, color="#2c3e50")
    ax.set_title("Mean Location Score by City")
    ax.set_xlabel("Location Score (0-100)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "location_score_by_city.png"), dpi=140)
    plt.close(fig)

    # Chart 3: location score vs accessibility score scatter
    fig, ax = plt.subplots(figsize=(6.5, 5))
    ax.scatter(df["accessibility_score"], df["location_score"], color="#2c3e50", alpha=0.7)
    ax.set_xlabel("Accessibility Score")
    ax.set_ylabel("Location Score")
    ax.set_title("Location Score vs. Accessibility Score")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "location_vs_accessibility.png"), dpi=140)
    plt.close(fig)

    # Chart 4: infrastructure delivery risk vs concentration risk
    fig, ax = plt.subplots(figsize=(6.5, 5))
    valid = df.dropna(subset=["delivery_risk", "concentration_risk"])
    ax.scatter(valid["delivery_risk"], valid["concentration_risk"], color="#c0392b", alpha=0.7)
    ax.set_xlabel("Infrastructure Delivery Risk (proxy, 0-100)")
    ax.set_ylabel("Infrastructure Concentration Risk (proxy, 0-100)")
    ax.set_title("Infrastructure Risk Proxies (n=%d localities with infra data)" % len(valid))
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "infra_risk_proxies.png"), dpi=140)
    plt.close(fig)

    print(f"Wrote 4 charts to {OUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["csv", "db"], default="db")
    args = parser.parse_args(args=[])
    main(source=args.source)