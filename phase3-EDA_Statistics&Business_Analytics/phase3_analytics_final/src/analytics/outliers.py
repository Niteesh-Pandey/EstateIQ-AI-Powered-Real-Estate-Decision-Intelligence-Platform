"""
Phase 2, §8 — Outlier Analysis
IQR + Z-score detection, with EVERY outlier group classified into one of:
  1. DATA_QUALITY_ERROR  — traceable to a generator bug, not a real market event
  2. LEGITIMATE_EXTREME  — a real, if unusual, observation
  3. SPECIAL_CASE        — plausible but warrants business context
  4. NEEDS_INVESTIGATION — can't be classified confidently from data alone

Outliers are NEVER deleted here — classification + counts only.
"""
import sys
import os
from pathlib import Path
import numpy as np

# --- Robust sys.path Resolution ---
try:
    current_dir = Path(__file__).resolve().parent
except NameError:
    current_dir = Path(os.getcwd()).resolve()

# Dynamically locate project folder containing connection.py
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

# --- Database Import & Search Path Configuration ---
from connection import get_cursor

def _configure_search_path():
    try:
        with get_cursor(dict_cursor=False) as cur:
            cur.execute("SET search_path TO core, analytics, public;")
    except Exception:
        pass

_configure_search_path()


def fetch_values(query: str) -> np.ndarray:
    with get_cursor(dict_cursor=False) as cur:
        cur.execute("SET search_path TO core, analytics, public;")
        cur.execute(query)
        res = cur.fetchall()
        if not res:
            return np.array([], dtype=float)
        return np.array([float(r[0]) for r in res if r[0] is not None])


def iqr_outliers(values: np.ndarray) -> dict:
    if len(values) == 0:
        return {"method": "IQR (1.5x)", "lower_bound": 0.0, "upper_bound": 0.0, "outlier_count": 0, "outlier_pct": 0.0, "n": 0}
    q1, q3 = np.percentile(values, [25, 75])
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    mask = (values < lower) | (values > upper)
    return {
        "method": "IQR (1.5x)", "lower_bound": round(lower, 2), "upper_bound": round(upper, 2),
        "outlier_count": int(mask.sum()), "outlier_pct": round(mask.sum() / len(values) * 100, 2),
        "n": len(values),
    }


def zscore_outliers(values: np.ndarray, threshold: float = 3.0) -> dict:
    if len(values) == 0:
        return {"method": f"Z-score (|z|>{threshold})", "outlier_count": 0, "outlier_pct": 0.0, "n": 0}
    mean, std = np.mean(values), np.std(values)
    if std == 0:
        return {"method": f"Z-score (|z|>{threshold})", "outlier_count": 0, "outlier_pct": 0.0, "n": len(values)}
    z = (values - mean) / std
    mask = np.abs(z) > threshold
    return {
        "method": f"Z-score (|z|>{threshold})", "mean": round(mean, 2), "std": round(std, 2),
        "outlier_count": int(mask.sum()), "outlier_pct": round(mask.sum() / len(values) * 100, 2),
        "n": len(values),
    }


def analyze_asking_price_outliers() -> dict:
    values = fetch_values("SELECT asking_price FROM properties WHERE asking_price IS NOT NULL;")
    return {
        "metric": "properties.asking_price", "iqr": iqr_outliers(values), "zscore": zscore_outliers(values),
        "classification": "LEGITIMATE_EXTREME",
        "evidence": "0.5% of properties.csv rows were generated with an intentional 2.5x price multiplier "
                     "to simulate real market premium/luxury listings (see data/generate_data_part2.py, "
                     "`out_idx` injection). This is a documented, deliberate design choice, not a bug.",
        "recommended_action": "Keep as-is. Represents luxury-segment properties; useful for testing "
                                "valuation model robustness to premium listings.",
    }


def analyze_transaction_price_outliers() -> dict:
    values = fetch_values("SELECT transaction_price FROM transactions WHERE transaction_price IS NOT NULL;")
    return {
        "metric": "transactions.transaction_price", "iqr": iqr_outliers(values), "zscore": zscore_outliers(values),
        "classification": "DATA_QUALITY_ERROR",
        "evidence": (
            "Root cause traced (see docs/eda_findings.md): transactions.price is computed as "
            "market_monthly.average_price_sqft * area_sqft. The price-growth formula in "
            "generate_data_part2.py (`psf = psf * (1 + growth)`) compounds monthly with NO ceiling "
            "or dampening. For localities with a persistently high demand/supply ratio, this causes "
            "runaway exponential growth — e.g. locality 28 goes from ₹13,592/sqft (2020-01) to "
            "₹1,923,519/sqft (2025-12), a 141x increase in 6 years. National avg price/sqft grew "
            "10,818 → 51,141 (YoY +90.8% in the final year) — statistically confirmed via skewness=12.2, "
            "excess kurtosis=172 on price_per_sqft (see distributions.py output)."
        ),
        "recommended_action": (
            "FIX AT SOURCE in a future data-regeneration phase: add a ceiling/mean-reversion term to "
            "the price-growth formula (e.g. cap monthly growth or add reversion toward a locality's "
            "income-implied price level). NOT fixed in this phase per Phase 2 scope (analytics/EDA only, "
            "no source-data modification). Flagged here for Phase 3+ remediation."
        ),
    }


def analyze_days_on_market_outliers() -> dict:
    values = fetch_values("SELECT days_on_market FROM listing_history WHERE days_on_market IS NOT NULL;")
    return {
        "metric": "listing_history.days_on_market", "iqr": iqr_outliers(values), "zscore": zscore_outliers(values),
        "classification": "NEEDS_INVESTIGATION",
        "evidence": "Already documented in docs/data_dictionary.md as having no feature-dependent signal "
                     "(DOM ML model R²=-0.04, near-random). Outliers here are as likely to be generator "
                     "noise as genuine slow-moving listings — cannot distinguish from data alone.",
        "recommended_action": "Do not use DOM outliers for business decisions (Model Registry already "
                                "blocks the DOM model at runtime — consistent treatment).",
    }


def analyze_rental_yield_outliers() -> dict:
    values = fetch_values("""
        SELECT (monthly_rent * 12 / NULLIF(asking_price,0)) * 100
        FROM properties WHERE monthly_rent IS NOT NULL AND asking_price > 0;
    """)
    return {
        "metric": "derived: gross_rental_yield_pct", "iqr": iqr_outliers(values), "zscore": zscore_outliers(values),
        "classification": "LEGITIMATE_EXTREME",
        "evidence": "Yield is generated as np.random.normal(3.3, 0.6) independently of price — a tight, "
                     "bounded distribution by construction (see generate_data_part2.py). IQR/Z-score "
                     "outliers here are simply the tails of that intentional normal distribution.",
        "recommended_action": "Keep as-is — expected statistical tail, not an error.",
    }


def run_full_outlier_analysis() -> list:
    return [
        analyze_asking_price_outliers(),
        analyze_transaction_price_outliers(),
        analyze_days_on_market_outliers(),
        analyze_rental_yield_outliers(),
    ]


if __name__ == "__main__":
    results = run_full_outlier_analysis()
    for r in results:
        print(f"=== {r['metric']} — {r['classification']} ===")
        print(f"  IQR outliers: {r['iqr']['outlier_count']} ({r['iqr']['outlier_pct']}%)")
        print(f"  Z-score outliers: {r['zscore']['outlier_count']} ({r['zscore']['outlier_pct']}%)")
        print(f"  Evidence: {r['evidence'][:150]}...")
        print()
