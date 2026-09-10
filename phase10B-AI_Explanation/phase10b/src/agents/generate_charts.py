"""
Phase 9 -- Chart Generator, matching Phase 3/5/6/7/8's docs/*_charts/ convention.
"""
import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(_HERE)), "docs", "decision_charts")

from batch_runner_decision import run_batch, build_tables


def main(source="db", n=25, sims=1000):
    os.makedirs(OUT_DIR, exist_ok=True)
    batch = run_batch(n=n, source=source, n_simulations=sims)
    tables = build_tables(batch)
    summary = tables["01_decision_summary"]
    components = tables["02_component_scores"]

    # Chart 1: decision distribution
    counts = summary["decision"].value_counts().reindex(["INVEST", "HOLD", "AVOID", "INSUFFICIENT"]).fillna(0)
    colors = {"INVEST": "#27ae60", "HOLD": "#f39c12", "AVOID": "#c0392b", "INSUFFICIENT": "#95a5a6"}
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    ax.bar(counts.index, counts.values, color=[colors[k] for k in counts.index])
    ax.set_title(f"Decision Distribution (demo batch, n={len(summary)})")
    ax.set_ylabel("Number of properties")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "decision_distribution.png"), dpi=140)
    plt.close(fig)

    # Chart 2: decision score vs confidence scatter, colored by decision
    fig, ax = plt.subplots(figsize=(7, 5.5))
    for label, color in colors.items():
        sub = summary[summary["decision"] == label]
        ax.scatter(sub["decision_score"], sub["decision_confidence"], color=color, label=label, s=60)
    ax.axhline(55, color="gray", linestyle="--", linewidth=0.8, label="Min confidence to act (55)")
    ax.axvline(65, color="gray", linestyle=":", linewidth=0.8, label="INVEST threshold (65)")
    ax.axvline(35, color="gray", linestyle=":", linewidth=0.8, label="AVOID threshold (35)")
    ax.set_xlabel("Decision Score (0-100)")
    ax.set_ylabel("Decision Confidence (0-100)")
    ax.set_title("Decision Score vs. Confidence (demo batch)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "score_vs_confidence.png"), dpi=140)
    plt.close(fig)

    # Chart 3: mean component score by component
    means = components.groupby("component")["score"].mean().sort_values()
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.barh(means.index, means.values, color="#2c3e50")
    ax.set_title("Mean Component Score Across Demo Batch")
    ax.set_xlabel("Score (0-100)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "mean_component_scores.png"), dpi=140)
    plt.close(fig)

    # Chart 4: component score heatmap (property x component)
    pivot = components.pivot(index="property_id", columns="component", values="score")
    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(pivot.values, cmap="RdYlGn", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=7)
    ax.set_title("Component Scores by Property (demo batch)")
    fig.colorbar(im, ax=ax, label="Score (0-100)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "component_score_heatmap.png"), dpi=140)
    plt.close(fig)

    print(f"Wrote 4 charts to {OUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["csv", "db"], default="db")
    parser.add_argument("--n", type=int, default=25)
    parser.add_argument("--sims", type=int, default=1000)
    args = parser.parse_args()
    main(source=args.source, n=args.n, sims=args.sims)
