"""
Phase 2, §2 — Data Quality Analysis
Reusable, table-agnostic data-quality profiler against the live
PostgreSQL database. No CSV dependency.
"""
import sys, os
sys.path.append(os.path.join(os.getcwd(), "..", "..", "db"))
from connection import get_cursor


def profile_numeric_column(table: str, column: str, schema: str = "public") -> dict:
    """Full numeric profile: nulls, duplicates, min/max/mean/median/std/percentiles."""
    with get_cursor() as cur:
        cur.execute(f"""
            SELECT
                COUNT(*) AS row_count,
                COUNT({column}) AS non_null_count,
                COUNT(*) - COUNT({column}) AS null_count,
                COUNT(DISTINCT {column}) AS unique_count,
                MIN({column}) AS min_val,
                MAX({column}) AS max_val,
                AVG({column}) AS mean_val,
                STDDEV({column}) AS std_val,
                PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY {column}) AS p25,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY {column}) AS median,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY {column}) AS p75,
                PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY {column}) AS p90,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY {column}) AS p95,
                PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY {column}) AS p99,
                COUNT(*) FILTER (WHERE {column} < 0) AS negative_count,
                COUNT(*) FILTER (WHERE {column} = 0) AS zero_count
            FROM {schema}.{table};
        """)
        row = dict(cur.fetchone())

    row["null_pct"] = round(row["null_count"] / row["row_count"] * 100, 2) if row["row_count"] else 0
    row["iqr"] = float(row["p75"]) - float(row["p25"]) if row["p75"] is not None and row["p25"] is not None else None
    row["coefficient_of_variation"] = (
        round(float(row["std_val"]) / float(row["mean_val"]), 3)
        if row["mean_val"] not in (None, 0) and row["std_val"] is not None else None
    )
    row["table"] = table
    row["column"] = column
    return row


def profile_categorical_column(table: str, column: str, schema: str = "public", top_n: int = 10) -> dict:
    """Cardinality, dominant/rare categories, null%."""
    with get_cursor() as cur:
        cur.execute(f"""
            SELECT COUNT(*) AS row_count, COUNT({column}) AS non_null_count,
                   COUNT(DISTINCT {column}) AS cardinality
            FROM {schema}.{table};
        """)
        base = dict(cur.fetchone())

        cur.execute(f"""
            SELECT {column} AS value, COUNT(*) AS n
            FROM {schema}.{table}
            WHERE {column} IS NOT NULL
            GROUP BY {column}
            ORDER BY n DESC
            LIMIT {top_n};
        """)
        top_categories = [dict(r) for r in cur.fetchall()]

    base["null_count"] = base["row_count"] - base["non_null_count"]
    base["null_pct"] = round(base["null_count"] / base["row_count"] * 100, 2) if base["row_count"] else 0
    base["top_categories"] = top_categories
    base["dominant_category"] = top_categories[0]["value"] if top_categories else None
    base["dominant_category_pct"] = (
        round(top_categories[0]["n"] / base["non_null_count"] * 100, 2)
        if top_categories and base["non_null_count"] else None
    )
    base["rare_categories"] = [c for c in top_categories if c["n"] / max(base["non_null_count"], 1) < 0.01]
    base["table"] = table
    base["column"] = column
    return base


def profile_date_column(table: str, column: str, schema: str = "public") -> dict:
    """Min/max date, future-date check, row count."""
    with get_cursor() as cur:
        cur.execute(f"""
            SELECT COUNT(*) AS row_count, COUNT({column}) AS non_null_count,
                   MIN({column}) AS min_date, MAX({column}) AS max_date,
                   COUNT(*) FILTER (WHERE {column} > CURRENT_DATE) AS future_date_count
            FROM {schema}.{table};
        """)
        row = dict(cur.fetchone())
    row["null_count"] = row["row_count"] - row["non_null_count"]
    row["table"] = table
    row["column"] = column
    return row


def check_duplicates(table: str, key_column: str, schema: str = "public") -> dict:
    with get_cursor() as cur:
        cur.execute(f"""
            SELECT COUNT(*) AS total_rows, COUNT(DISTINCT {key_column}) AS unique_keys
            FROM {schema}.{table};
        """)
        row = dict(cur.fetchone())
    row["duplicate_count"] = row["total_rows"] - row["unique_keys"]
    row["table"] = table
    return row


def referential_integrity_check(child_table: str, fk_column: str, parent_table: str, pk_column: str,
                                 schema: str = "public") -> dict:
    """Counts orphan rows in child_table.fk_column not present in parent_table.pk_column."""
    with get_cursor() as cur:
        cur.execute(f"""
            SELECT COUNT(*) AS orphan_count
            FROM {schema}.{child_table} c
            WHERE c.{fk_column} IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM {schema}.{parent_table} p WHERE p.{pk_column} = c.{fk_column}
              );
        """)
        orphan_count = cur.fetchone()["orphan_count"]
    return {"child": child_table, "fk": fk_column, "parent": parent_table, "orphan_count": orphan_count}


# Pre-defined profile targets for the key real-estate metrics (§3 of the spec)
KEY_NUMERIC_COLUMNS = [
    ("properties", "asking_price"), ("properties", "monthly_rent"), ("properties", "area_sqft"),
    ("properties", "bedrooms"), ("transactions", "transaction_price"), ("transactions", "price_per_sqft"),
    ("listing_history", "days_on_market"), ("market_monthly", "demand_index"),
    ("market_monthly", "supply_index"), ("market_monthly", "available_inventory"),
    ("market_monthly", "units_sold"), ("rentals", "monthly_rent"),
]

KEY_CATEGORICAL_COLUMNS = [
    ("properties", "property_type"), ("properties", "furnishing"),
    ("listing_history", "status"), ("transactions", "buyer_type"),
    ("transactions", "transaction_type"), ("projects", "project_status"),
]

KEY_DATE_COLUMNS = [
    ("transactions", "transaction_date"), ("rentals", "rental_date"),
    ("listing_history", "listing_date"), ("property_events", "event_date"),
]

FK_CHECKS = [
    ("localities", "city_id", "cities", "city_id"),
    ("projects", "developer_id", "developers", "developer_id"),
    ("projects", "locality_id", "localities", "locality_id"),
    ("properties", "project_id", "projects", "project_id"),
    ("transactions", "property_id", "properties", "property_id"),
    ("rentals", "property_id", "properties", "property_id"),
]


def run_full_data_quality_report() -> dict:
    return {
        "numeric_profiles": [profile_numeric_column(t, c) for t, c in KEY_NUMERIC_COLUMNS],
        "categorical_profiles": [profile_categorical_column(t, c) for t, c in KEY_CATEGORICAL_COLUMNS],
        "date_profiles": [profile_date_column(t, c) for t, c in KEY_DATE_COLUMNS],
        "referential_integrity": [referential_integrity_check(*fk) for fk in FK_CHECKS],
    }


if __name__ == "__main__":
    import json
    report = run_full_data_quality_report()
    print("=== Sample numeric profile: properties.asking_price ===")
    print(json.dumps(report["numeric_profiles"][0], indent=2, default=str))
    print("\n=== Sample categorical profile: properties.property_type ===")
    print(json.dumps(report["categorical_profiles"][0], indent=2, default=str))
    print("\n=== Referential integrity (should all be 0) ===")
    for r in report["referential_integrity"]:
        print(f"  {r['child']}.{r['fk']} -> {r['parent']}: {r['orphan_count']} orphans")
