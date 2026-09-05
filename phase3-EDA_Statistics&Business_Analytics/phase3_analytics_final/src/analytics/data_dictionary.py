"""
Phase 2, §1 — Data Dictionary Builder
Introspects the LIVE PostgreSQL schema (information_schema) and pairs each
column with its business meaning. Business meaning text is authored based
on the known data-generation logic (data/generate_data.py) — not invented
guesses about an unknown dataset.
"""
import sys, os
sys.path.append(os.path.join(os.getcwd(), "..", "..", "db"))
from connection import get_cursor
import json

# Business meaning is documented per-column, keyed by (table, column).
# Source of truth: data/generate_data.py / generate_data_part2.py and
# sql/01_schema.sql — not fabricated for unknown fields.
BUSINESS_MEANING = {
    ("cities", "development_score"): "0-100 composite index of city-level development (income, infra)",
    ("localities", "connectivity_score"): "0-100 transit/road connectivity quality",
    ("localities", "development_score"): "0-100 composite: 0.3*connectivity + 0.3*infra + 0.2*safety + 0.2*commercial",
    ("localities", "commercial_score"): "0-100 density of commercial/business activity",
    ("developers", "delivery_score"): "0-100 track record of on-time/quality project delivery",
    ("developers", "market_share"): "% share of total units across all projects in the dataset",
    ("projects", "units_sold"): "Cumulative units sold as of data generation date (not time-series)",
    ("properties", "asking_price"): "Current listed price in INR (₹); 0.5% of rows have 2.5x outlier injected",
    ("properties", "monthly_rent"): "Current monthly rent in INR; ~2% missing (injected, realistic)",
    ("properties", "age_years"): "Years since project launch",
    ("transactions", "transaction_price"): "Actual sale price at transaction_date, distinct from current asking_price",
    ("transactions", "price_per_sqft"): "transaction_price / area_sqft, computed at generation time",
    ("rentals", "vacancy_days"): "Days the unit sat vacant before this rental began",
    ("listing_history", "days_on_market"): "Days between listing_date and sale/expiry; KNOWN WEAK SIGNAL (see docs/data_dictionary.md — generated independent of property features)",
    ("market_monthly", "demand_index"): "0-100 locality-month demand proxy, influenced by interest rates",
    ("market_monthly", "supply_index"): "0-100 locality-month supply proxy",
    ("market_monthly", "absorption_rate"): "units_sold / available_inventory for that locality-month",
    ("market_monthly", "average_days_on_market"): "Locality-month average DOM (aggregate signal, separate from listing_history.days_on_market)",
    ("economic_monthly", "interest_rate"): "Annual mortgage-adjacent interest rate (%), random-walk generated",
    ("infrastructure", "impact_score"): "0-100 relevance of this infra point to nearby localities",
    ("property_events", "event_type"): "Funnel stage: View/Inquiry/Lead/Site Visit/Booking/Cancellation",
    ("expenses", "management_cost"): "Property management fee, computed as 8% of monthly_rent at generation time",
}


def build_data_dictionary() -> list:
    with get_cursor() as cur:
        cur.execute("""
            SELECT table_name, column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position;
        """)
        rows = [dict(r) for r in cur.fetchall()]

    for r in rows:
        key = (r["table_name"], r["column_name"])
        r["business_meaning"] = BUSINESS_MEANING.get(
            key, "Structural/identifier field — see sql/01_schema.sql for FK relationships"
            if r["column_name"].endswith("_id") else "See table context; no special business logic beyond raw value")
        r["analytical_use"] = _infer_analytical_use(r)
        r["missing_value_behavior"] = "NULLABLE — real missingness possible" if r["is_nullable"] == "YES" else "NOT NULL — no missingness expected"
    return rows


def _infer_analytical_use(row) -> str:
    dtype = row["data_type"]
    name = row["column_name"]
    if name.endswith("_id"):
        return "Join key / grouping dimension"
    if dtype in ("numeric", "integer", "bigint"):
        if "score" in name or "index" in name or "rate" in name or "pct" in name:
            return "Descriptive stats, correlation, segmentation KPI"
        if "price" in name or "rent" in name or "cost" in name or "tax" in name:
            return "Descriptive stats, distribution analysis, outlier detection"
        return "Descriptive stats"
    if dtype == "date" or name == "month":
        return "Time-series analysis (trend, YoY/MoM, seasonality)"
    if dtype == "text":
        return "Segmentation dimension / categorical analysis"
    return "General"


if __name__ == "__main__":
    d = build_data_dictionary()
    print(f"Data dictionary: {len(d)} columns documented across core schema.\n")
    for r in d[:8]:
        print(json.dumps(r, indent=2))
        print()
