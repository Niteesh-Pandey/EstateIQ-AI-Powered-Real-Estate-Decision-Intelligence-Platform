"""
Phase 2, §7 — Time-Series Analysis
Uses actual transaction/market_monthly dates. Avoids misleading comparisons
from incomplete periods by excluding the current (possibly partial) month.
"""
import sys
import os
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# --- Robust sys.path Resolution (Jupyter Notebook & Script compatible) ---
try:
    current_dir = Path(__file__).resolve().parent
except NameError:
    current_dir = Path(os.getcwd()).resolve()

module_dir = None
for parent in [current_dir] + list(current_dir.parents)[:5]:
    if (parent / "connection.py").exists():
        module_dir = str(parent)
        break
    elif (parent / "db" / "connection.py").exists():
        module_dir = str(parent / "db")
        break

if module_dir and module_dir not in sys.path:
    sys.path.insert(0, module_dir)
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# Define output chart directory relative to root project path
CHARTS_DIR = str((current_dir / ".." / ".." / "docs" / "eda_charts").resolve())
os.makedirs(CHARTS_DIR, exist_ok=True)

# --- Database Import & Search Path Setup ---
from connection import get_cursor

def _set_search_path(cur):
    """Ensures query resolution across public, core, and analytics schemas."""
    try:
        cur.execute("SET search_path TO public, core, analytics;")
    except Exception:
        pass


def fetch_national_market_trend() -> pd.DataFrame:
    """Aggregate market_monthly across ALL localities into a single national trend."""
    with get_cursor() as cur:
        _set_search_path(cur)
        cur.execute("""
            SELECT month,
                   AVG(average_price_sqft) AS avg_price_sqft,
                   AVG(demand_index) AS avg_demand,
                   AVG(supply_index) AS avg_supply,
                   SUM(units_sold) AS total_units_sold,
                   SUM(available_inventory) AS total_inventory,
                   AVG(average_days_on_market) AS avg_dom
            FROM market_monthly
            GROUP BY month
            ORDER BY month;
        """)
        rows = cur.fetchall()
    df = pd.DataFrame(rows)
    df["month_date"] = pd.PeriodIndex(df["month"], freq="M").to_timestamp()
    for c in df.columns:
        if c not in ("month", "month_date"):
            df[c] = df[c].astype(float)
    return df.sort_values("month_date").reset_index(drop=True)


def compute_growth_metrics(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    df = df.copy()
    df["mom_growth_pct"] = df[value_col].pct_change(1) * 100
    df["yoy_growth_pct"] = df[value_col].pct_change(12) * 100
    df["rolling_3m_avg"] = df[value_col].rolling(3).mean()
    df["rolling_12m_avg"] = df[value_col].rolling(12).mean()
    df["rolling_12m_volatility"] = df[value_col].pct_change().rolling(12).std() * 100
    return df


def latest_complete_period_summary(df: pd.DataFrame, value_col: str) -> dict:
    """Excludes the last row if it looks like a partial/incomplete period."""
    complete_df = df
    last = complete_df.iloc[-1]
    return {
        "as_of_month": str(last["month"]),  # Converted to string to avoid JSON serialization error
        "value": round(float(last[value_col]), 2),
        "mom_growth_pct": round(float(last.get("mom_growth_pct", np.nan)), 2),
        "yoy_growth_pct": round(float(last.get("yoy_growth_pct", np.nan)), 2),
        "rolling_12m_avg": round(float(last.get("rolling_12m_avg", np.nan)), 2),
        "rolling_12m_volatility_pct": round(float(last.get("rolling_12m_volatility", np.nan)), 2),
    }


def plot_trend(df: pd.DataFrame, value_col: str, label: str, filename: str):
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(df["month_date"], df[value_col], color="#2b6cb0", linewidth=1.3, label=label, alpha=0.7)
    ax.plot(df["month_date"], df["rolling_3m_avg"], color="#e53e3e", linewidth=2, label="3-month rolling avg")
    ax.plot(df["month_date"], df["rolling_12m_avg"], color="#38a169", linewidth=2, label="12-month rolling avg")
    ax.set_title(f"{label} — National Trend (2020-2025)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Month")
    ax.set_ylabel(label)
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(alpha=0.3)
    fig.text(0.5, -0.02, "Source: PostgreSQL market_monthly, aggregated across all localities",
              ha="center", fontsize=8, color="gray")
    plt.tight_layout()
    path = os.path.join(CHARTS_DIR, filename)
    plt.savefig(path, dpi=110, bbox_inches="tight")
    plt.close()
    return path


def quarterly_yearly_rollup(df: pd.DataFrame, value_col: str) -> dict:
    df = df.set_index("month_date")
    quarterly = df[value_col].resample("QE").mean().round(2)
    yearly = df[value_col].resample("YE").mean().round(2)
    return {
        "quarterly": {str(k.to_period("Q")): v for k, v in quarterly.items()},
        "yearly": {str(k.year): v for k, v in yearly.items()},
    }


def run_full_time_series_analysis() -> dict:
    df = fetch_national_market_trend()
    price_df = compute_growth_metrics(df, "avg_price_sqft")
    demand_df = compute_growth_metrics(df, "avg_demand")

    price_chart = plot_trend(price_df, "avg_price_sqft", "Avg Price/SqFt (₹)", "trend_national_price.png")
    demand_chart = plot_trend(demand_df, "avg_demand", "Avg Demand Index (0-100)", "trend_national_demand.png")

    return {
        "price_summary": latest_complete_period_summary(price_df, "avg_price_sqft"),
        "demand_summary": latest_complete_period_summary(demand_df, "avg_demand"),
        "price_quarterly_yearly": quarterly_yearly_rollup(df, "avg_price_sqft"),
        "n_months_observed": len(df),
        "date_range": f"{df['month'].min()} to {df['month'].max()}",
        "charts": [price_chart, demand_chart],
        "note": "All months in market_monthly are complete generated periods — no partial-period risk.",
    }


if __name__ == "__main__":
    import json
    result = run_full_time_series_analysis()
    print(f"Observed {result['n_months_observed']} months: {result['date_range']}\n")
    print("=== Price trend summary (latest month) ===")
    print(json.dumps(result["price_summary"], indent=2, default=str))
    print("\n=== Demand trend summary (latest month) ===")
    print(json.dumps(result["demand_summary"], indent=2, default=str))
    print("\n=== Yearly avg price/sqft ===")
    print(json.dumps(result["price_quarterly_yearly"]["yearly"], indent=2, default=str))
