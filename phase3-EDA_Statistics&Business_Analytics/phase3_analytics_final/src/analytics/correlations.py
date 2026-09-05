"""
Phase 2, §5 — Correlation Analysis
Pearson (linear) + Spearman (monotonic/rank) correlation between
meaningful numerical variables, pulled jointly from PostgreSQL so pairs
are correctly aligned (not independently sampled columns).

IMPORTANT: correlation does not imply causation. All outputs from this
module must be read with that caveat — enforced by including the caveat
string in every result dict, not just this docstring.
"""
import sys, os
sys.path.append(os.path.join(os.getcwd(), "..", "..", "db"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
from scipy import stats
from connection import get_cursor

CHARTS_DIR = os.path.join(os.getcwd(), "..", "..", "docs", "eda_charts")
os.makedirs(CHARTS_DIR, exist_ok=True)
CAVEAT = "Correlation does not imply causation. These are observed statistical associations only."


def fetch_joined_property_data() -> pd.DataFrame:
    """Property + locality + market features, joined at the property level."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT
                p.property_id, p.area_sqft, p.bedrooms, p.asking_price, p.monthly_rent,
                p.age_years, l.connectivity_score, l.infrastructure_score, l.development_score,
                m.demand_index, m.supply_index, m.average_days_on_market
            FROM properties p
            JOIN projects pj ON pj.project_id = p.project_id
            JOIN localities l ON l.locality_id = pj.locality_id
            LEFT JOIN LATERAL (
                SELECT demand_index, supply_index, average_days_on_market
                FROM market_monthly mm
                WHERE mm.locality_id = pj.locality_id
                ORDER BY mm.month DESC LIMIT 1
            ) m ON TRUE
            WHERE p.monthly_rent IS NOT NULL;
        """)
        rows = cur.fetchall()
    return pd.DataFrame(rows).astype(float)


def fetch_market_time_series() -> pd.DataFrame:
    """Locality-month level: demand, supply, price, DOM, interest rate (joined)."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT m.locality_id, m.month, m.average_price_sqft, m.demand_index,
                   m.supply_index, m.units_sold, m.available_inventory,
                   m.average_days_on_market, e.interest_rate
            FROM market_monthly m
            JOIN economic_monthly e ON e.month = m.month;
        """)
        rows = cur.fetchall()
    df = pd.DataFrame(rows)
    for c in df.columns:
        if c not in ("locality_id", "month"):
            df[c] = df[c].astype(float)
    return df


def compute_correlation_matrix(df: pd.DataFrame, method: str = "pearson") -> pd.DataFrame:
    return df.corr(method=method)


def top_correlations(df: pd.DataFrame, method: str = "pearson", n: int = 10) -> list:
    corr = compute_correlation_matrix(df, method)
    pairs = []
    cols = corr.columns
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            val = corr.iloc[i, j]
            if pd.notna(val):
                pairs.append({"var1": cols[i], "var2": cols[j], "correlation": round(float(val), 3),
                              "method": method, "caveat": CAVEAT})
    pairs_sorted = sorted(pairs, key=lambda x: abs(x["correlation"]), reverse=True)
    return pairs_sorted[:n]


def plot_correlation_heatmap(df: pd.DataFrame, filename: str, title: str, method: str = "pearson"):
    corr = compute_correlation_matrix(df, method)
    plt.figure(figsize=(9, 7))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r", center=0, vmin=-1, vmax=1,
                square=True, cbar_kws={"label": f"{method.title()} correlation"})
    plt.title(f"{title}\n({method.title()} correlation | correlation ≠ causation)", fontsize=11, fontweight="bold")
    plt.tight_layout()
    path = os.path.join(CHARTS_DIR, filename)
    plt.savefig(path, dpi=110, bbox_inches="tight")
    plt.close()
    return path


def spearman_vs_pearson_divergence(df: pd.DataFrame, var1: str, var2: str) -> dict:
    """Where Spearman and Pearson disagree substantially, the relationship is
    likely monotonic-but-nonlinear (or driven by outliers) — flag it."""
    x, y = df[var1].dropna(), df[var2].dropna()
    common_idx = x.index.intersection(y.index)
    x, y = df.loc[common_idx, var1], df.loc[common_idx, var2]
    pearson_r, pearson_p = stats.pearsonr(x, y)
    spearman_r, spearman_p = stats.spearmanr(x, y)
    return {
        "var1": var1, "var2": var2,
        "pearson_r": round(pearson_r, 3), "pearson_p": round(pearson_p, 5),
        "spearman_r": round(spearman_r, 3), "spearman_p": round(spearman_p, 5),
        "divergence": round(abs(pearson_r - spearman_r), 3),
        "interpretation": (
            "Similar — relationship is roughly linear" if abs(pearson_r - spearman_r) < 0.1
            else "Diverges — relationship likely nonlinear/monotonic or outlier-influenced"
        ),
        "caveat": CAVEAT,
    }


def run_full_correlation_analysis() -> dict:
    prop_df = fetch_joined_property_data()
    market_df = fetch_market_time_series().drop(columns=["locality_id", "month"])

    prop_pearson_path = plot_correlation_heatmap(
        prop_df, "correlation_property_features.png", "Property & Locality Feature Correlations", "pearson")
    market_pearson_path = plot_correlation_heatmap(
        market_df, "correlation_market_features.png", "Market-Level Feature Correlations (locality-month)", "pearson")

    return {
        "property_level": {
            "top_pearson": top_correlations(prop_df, "pearson", 8),
            "top_spearman": top_correlations(prop_df, "spearman", 8),
            "heatmap": prop_pearson_path,
        },
        "market_level": {
            "top_pearson": top_correlations(market_df, "pearson", 8),
            "top_spearman": top_correlations(market_df, "spearman", 8),
            "heatmap": market_pearson_path,
        },
        "area_vs_price_check": spearman_vs_pearson_divergence(prop_df, "area_sqft", "asking_price"),
        "demand_vs_dom_check": spearman_vs_pearson_divergence(market_df, "demand_index", "average_days_on_market"),
        "interest_rate_vs_demand_check": spearman_vs_pearson_divergence(market_df, "interest_rate", "demand_index"),
        "caveat": CAVEAT,
    }


if __name__ == "__main__":
    import json
    result = run_full_correlation_analysis()
    print("=== Top Pearson correlations (property level) ===")
    for c in result["property_level"]["top_pearson"]:
        print(f"  {c['var1']:25} <-> {c['var2']:25} r={c['correlation']:>6.3f}")
    print("\n=== Top Pearson correlations (market level) ===")
    for c in result["market_level"]["top_pearson"]:
        print(f"  {c['var1']:25} <-> {c['var2']:25} r={c['correlation']:>6.3f}")
    print("\n=== Interest rate vs demand (expected negative per data-gen logic) ===")
    print(json.dumps(result["interest_rate_vs_demand_check"], indent=2))
