"""
Phase 2, §4 — Distribution Analysis
Skewness/kurtosis via scipy.stats, plus histogram+boxplot visualizations
saved to docs/eda_charts/. Data pulled directly from PostgreSQL (no CSV).
"""
import sys, os
sys.path.append(os.path.join(os.getcwd(), "..", "..", "db"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from scipy import stats
from connection import get_cursor

CHARTS_DIR = os.path.join(os.getcwd(), "..", "..", "docs", "eda_charts")
os.makedirs(CHARTS_DIR, exist_ok=True)

sns.set_style("whitegrid")


def fetch_column_values(table: str, column: str, schema: str = "public", where: str = None) -> np.ndarray:
    query = f"SELECT {column} FROM {schema}.{table} WHERE {column} IS NOT NULL"
    if where:
        query += f" AND {where}"
    with get_cursor(dict_cursor=False) as cur:
        cur.execute(query + ";")
        vals = [float(r[0]) for r in cur.fetchall()]
    return np.array(vals)


def analyze_distribution(table: str, column: str, label: str, schema: str = "public", where: str = None) -> dict:
    values = fetch_column_values(table, column, schema, where)
    skewness = float(stats.skew(values))
    kurt = float(stats.kurtosis(values))  # excess kurtosis (0 = normal)

    def shape_desc(sk):
        if abs(sk) < 0.5:
            return "approximately symmetric"
        elif sk >= 0.5:
            return "right-skewed (long tail toward high values)" if sk < 1 else "strongly right-skewed"
        else:
            return "left-skewed (long tail toward low values)" if sk > -1 else "strongly left-skewed"

    def tail_desc(k):
        if k > 1:
            return "heavy-tailed (more extreme outliers than a normal distribution)"
        elif k < -1:
            return "light-tailed (fewer extreme outliers than a normal distribution)"
        return "approximately normal tail weight"

    return {
        "table": table, "column": column, "label": label, "n": len(values),
        "skewness": round(skewness, 3), "shape": shape_desc(skewness),
        "excess_kurtosis": round(kurt, 3), "tail_behavior": tail_desc(kurt),
        "mean": round(float(np.mean(values)), 2), "median": round(float(np.median(values)), 2),
    }


def plot_distribution(table: str, column: str, label: str, filename: str,
                       schema: str = "public", where: str = None, log_scale: bool = False):
    """Histogram + boxplot side-by-side. Every chart answers: 'what does this
    metric's distribution actually look like, and where are the outliers?'"""
    values = fetch_column_values(table, column, schema, where)
    if log_scale:
        values_plot = values[values > 0]
        xlabel = f"{label} (log scale)"
    else:
        values_plot = values
        xlabel = label

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    ax1, ax2 = axes

    sns.histplot(values_plot, kde=True, ax=ax1, color="#2b6cb0", log_scale=log_scale)
    ax1.set_title(f"Distribution: {label}", fontsize=11, fontweight="bold")
    ax1.set_xlabel(xlabel)
    ax1.set_ylabel("Count")

    sns.boxplot(x=values_plot, ax=ax2, color="#63b3ed")
    ax2.set_title(f"Box Plot: {label}\n(IQR outlier view)", fontsize=11, fontweight="bold")
    ax2.set_xlabel(xlabel)
    if log_scale:
        ax2.set_xscale("log")

    fig.suptitle(f"n={len(values):,} | Source: PostgreSQL {schema}.{table}.{column}", fontsize=9, y=1.02, color="gray")
    plt.tight_layout()
    path = os.path.join(CHARTS_DIR, filename)
    plt.savefig(path, dpi=110, bbox_inches="tight")
    plt.close()
    return path


DISTRIBUTION_TARGETS = [
    ("properties", "asking_price", "Asking Price (₹)", "dist_asking_price.png", False),
    ("properties", "area_sqft", "Property Area (sqft)", "dist_area_sqft.png", False),
    ("properties", "monthly_rent", "Monthly Rent (₹)", "dist_monthly_rent.png", False),
    ("transactions", "price_per_sqft", "Transaction Price/SqFt (₹)", "dist_price_per_sqft.png", True),
    ("listing_history", "days_on_market", "Days on Market", "dist_days_on_market.png", False),
    ("market_monthly", "demand_index", "Demand Index (0-100)", "dist_demand_index.png", False),
]


def run_full_distribution_analysis() -> list:
    results = []
    for table, col, label, fname, log in DISTRIBUTION_TARGETS:
        stats_row = analyze_distribution(table, col, label)
        stats_row["chart_path"] = plot_distribution(table, col, label, fname, log_scale=log)
        results.append(stats_row)
    return results


if __name__ == "__main__":
    results = run_full_distribution_analysis()
    for r in results:
        print(f"{r['label']:35} skew={r['skewness']:>7.3f} ({r['shape']:35}) "
              f"excess_kurtosis={r['excess_kurtosis']:>7.3f} ({r['tail_behavior']})")
        print(f"  -> chart saved: {r['chart_path']}")
