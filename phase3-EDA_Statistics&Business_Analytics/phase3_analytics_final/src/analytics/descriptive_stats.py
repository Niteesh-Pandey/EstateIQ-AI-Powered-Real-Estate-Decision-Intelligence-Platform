"""
Phase 2, §3 — Descriptive Statistics
Thin, business-readable wrapper over data_quality.profile_numeric_column
for the specific metrics called out in the spec (price, rent, yield, area,
DOM, demand, supply, etc.) Reuses the same PostgreSQL-backed profiler —
no duplicate SQL logic.
"""
import sys, os
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "..", "..", "db"))
from data_quality import profile_numeric_column
from connection import get_cursor

METRICS = [
    ("properties", "asking_price", "Property asking price (₹)"),
    ("properties", "monthly_rent", "Property monthly rent (₹)"),
    ("properties", "area_sqft", "Property area (sqft)"),
    ("transactions", "transaction_price", "Actual transaction price (₹)"),
    ("transactions", "price_per_sqft", "Transaction price per sqft (₹)"),
    ("listing_history", "days_on_market", "Days on market (listing to sale/expiry)"),
    ("market_monthly", "demand_index", "Locality-month demand index (0-100)"),
    ("market_monthly", "supply_index", "Locality-month supply index (0-100)"),
    ("market_monthly", "available_inventory", "Available inventory (units)"),
    ("market_monthly", "units_sold", "Units sold per locality-month"),
]


def rental_yield_stats() -> dict:
    """Rental yield isn't a raw column — compute it inline from properties, then profile."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT
                COUNT(*) AS row_count,
                AVG(yield_pct) AS mean_val,
                STDDEV(yield_pct) AS std_val,
                MIN(yield_pct) AS min_val,
                MAX(yield_pct) AS max_val,
                PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY yield_pct) AS p25,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY yield_pct) AS median,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY yield_pct) AS p75,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY yield_pct) AS p95
            FROM (
                SELECT (monthly_rent * 12 / NULLIF(asking_price, 0)) * 100 AS yield_pct
                FROM properties
                WHERE monthly_rent IS NOT NULL AND asking_price > 0
            ) t;
        """)
        row = dict(cur.fetchone())
    row["table"] = "properties (derived)"
    row["column"] = "gross_rental_yield_pct"
    return row


def build_descriptive_stats_table() -> list:
    results = [profile_numeric_column(t, c) for t, c, _ in METRICS]
    labels = {(t, c): label for t, c, label in METRICS}
    for r in results:
        r["label"] = labels[(r["table"], r["column"])]
    results.append({**rental_yield_stats(), "label": "Gross rental yield (%)"})
    return results


def print_summary_table(results: list):
    print(f"{'Metric':45} {'N':>7} {'Mean':>14} {'Median':>14} {'Std':>12} {'P95':>14} {'CV':>6}")
    print("-" * 115)
    for r in results:
        cv = r.get("coefficient_of_variation")
        cv_str = f"{cv:.2f}" if cv is not None else "n/a"
        print(f"{r['label']:45} {r['row_count']:>7} {float(r['mean_val']):>14,.1f} "
              f"{float(r['median']):>14,.1f} {float(r['std_val'] or 0):>12,.1f} "
              f"{float(r['p95'] or 0):>14,.1f} {cv_str:>6}")


if __name__ == "__main__":
    results = build_descriptive_stats_table()
    print_summary_table(results)
