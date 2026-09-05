"""
=====================================================================
 REAL ESTATE DATASET CLEANER
=====================================================================
Yeh script 14 CSV files ko clean karta hai (Real Estate market data:
cities, localities, properties, transactions, rentals, etc.)

SIMPLE EXPLANATION (English):
This script reads every CSV file, checks it for common data problems,
fixes the ones that are safe to auto-fix, FLAGS the ones that need a
human decision (instead of silently deleting data), and writes clean
files into an output folder. It also prints/saves a report so you can
see exactly what was changed and why.

WHAT "CLEANING" MEANS HERE (5 simple steps, done for every file):
  1. TRIM WHITESPACE  -> remove extra spaces around text (" Pune " -> "Pune")
  2. FIX DATA TYPES    -> make sure dates are real dates, numbers are numbers
  3. REMOVE DUPLICATES -> drop exact duplicate rows / duplicate ID rows
  4. HANDLE MISSING VALUES -> report them, and only fill when it's safe
  5. FIX LOGICAL ERRORS -> e.g. a flat's floor number cannot be higher than
     the building's total floors -> we cap it
  6. FLAG OUTLIERS      -> unusually high/low prices are marked in a new
     column (is_price_outlier) instead of being deleted, so you can
     review them yourself later.

RUN:
    python3 clean_real_estate_data.py

INPUT  : ./ (same folder as this script) - the 14 raw CSV files
OUTPUT : ./cleaned/               -> cleaned CSV files
         ./cleaning_report.txt    -> plain-English summary of every fix
=====================================================================
"""

import pandas as pd
import numpy as np
import os

INPUT_DIR = "."
OUTPUT_DIR = "./cleaned"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# This list collects one line of plain-English notes per action,
# so at the end we can print/save a full report.
report_lines = []


def log(msg):
    """Print AND save a report line."""
    print(msg)
    report_lines.append(msg)


def section(title):
    log("\n" + "=" * 70)
    log(title)
    log("=" * 70)


# ---------------------------------------------------------------
# GENERIC HELPER FUNCTIONS (reused for every file)
# ---------------------------------------------------------------

def trim_whitespace(df, filename):
    """Remove leading/trailing spaces from all text columns."""
    text_cols = df.select_dtypes(include=["object", "str"]).columns
    changed = 0
    for col in text_cols:
        before = df[col].astype(str)
        after = before.str.strip()
        changed += (before != after).sum()
        df[col] = after
    if changed:
        log(f"  - {filename}: trimmed extra spaces in {changed} cell(s)")
    return df


def drop_duplicate_rows(df, filename):
    """Remove fully duplicated rows (every column identical)."""
    before = len(df)
    df = df.drop_duplicates()
    removed = before - len(df)
    if removed:
        log(f"  - {filename}: removed {removed} fully duplicate row(s)")
    return df


def drop_duplicate_ids(df, filename, id_col):
    """Remove rows with a duplicate primary key (keep first occurrence)."""
    if id_col not in df.columns:
        return df
    before = len(df)
    df = df.drop_duplicates(subset=[id_col], keep="first")
    removed = before - len(df)
    if removed:
        log(f"  - {filename}: removed {removed} row(s) with duplicate {id_col}")
    return df


def parse_dates(df, filename, date_cols):
    """Convert date columns from text to real datetime type."""
    for col in date_cols:
        if col in df.columns:
            before_na = df[col].isna().sum()
            df[col] = pd.to_datetime(df[col], errors="coerce")
            after_na = df[col].isna().sum()
            bad = after_na - before_na
            if bad > 0:
                log(f"  - {filename}: {bad} value(s) in '{col}' could not be "
                    f"read as a date and were set to empty (please check source)")
    return df


def report_missing(df, filename):
    """Just report which columns have missing (null) values."""
    nulls = df.isnull().sum()
    nulls = nulls[nulls > 0]
    if len(nulls):
        for col, n in nulls.items():
            log(f"  - {filename}: column '{col}' has {n} missing value(s)")
    return df


def flag_price_outliers(df, filename, price_col, flag_col="is_price_outlier"):
    """
    Mark unusually high/low prices using the IQR (Inter-Quartile Range) method
    instead of deleting them. This keeps the data safe while still telling you
    which rows deserve a manual look (could be genuine luxury property, or
    could be a data-entry mistake -- a human should decide).
    """
    if price_col not in df.columns:
        return df
    q1, q3 = df[price_col].quantile([0.25, 0.75])
    iqr = q3 - q1
    low_fence = q1 - 1.5 * iqr
    high_fence = q3 + 1.5 * iqr
    df[flag_col] = (df[price_col] < low_fence) | (df[price_col] > high_fence)
    n_flagged = df[flag_col].sum()
    if n_flagged:
        log(f"  - {filename}: flagged {n_flagged} row(s) in '{price_col}' as "
            f"statistical outliers (kept in data, just marked for review)")
    return df


# ---------------------------------------------------------------
# 1. cities.csv
# ---------------------------------------------------------------
section("1/14 Cleaning cities.csv")
df = pd.read_csv(f"{INPUT_DIR}/cities.csv")
df = trim_whitespace(df, "cities.csv")
df = drop_duplicate_rows(df, "cities.csv")
df = drop_duplicate_ids(df, "cities.csv", "city_id")
df = report_missing(df, "cities.csv")
df.to_csv(f"{OUTPUT_DIR}/cities.csv", index=False)
log("  -> saved cleaned/cities.csv")

# ---------------------------------------------------------------
# 2. developers.csv
# ---------------------------------------------------------------
section("2/14 Cleaning developers.csv")
df = pd.read_csv(f"{INPUT_DIR}/developers.csv")
df = trim_whitespace(df, "developers.csv")
df = drop_duplicate_rows(df, "developers.csv")
df = drop_duplicate_ids(df, "developers.csv", "developer_id")
df = report_missing(df, "developers.csv")
df.to_csv(f"{OUTPUT_DIR}/developers.csv", index=False)
log("  -> saved cleaned/developers.csv")

# ---------------------------------------------------------------
# 3. documents.csv
# ---------------------------------------------------------------
section("3/14 Cleaning documents.csv")
df = pd.read_csv(f"{INPUT_DIR}/documents.csv")
df = trim_whitespace(df, "documents.csv")
df = drop_duplicate_rows(df, "documents.csv")
df = drop_duplicate_ids(df, "documents.csv", "document_id")
df = parse_dates(df, "documents.csv", ["document_date"])
# 'embedding' column is 100% empty in every row -> it carries no
# information, so we drop it to keep the file honest and clean.
if "embedding" in df.columns and df["embedding"].isnull().all():
    df = df.drop(columns=["embedding"])
    log("  - documents.csv: dropped 'embedding' column (was 100% empty)")
df = report_missing(df, "documents.csv")
df.to_csv(f"{OUTPUT_DIR}/documents.csv", index=False)
log("  -> saved cleaned/documents.csv")

# ---------------------------------------------------------------
# 4. economic_monthly.csv
# ---------------------------------------------------------------
section("4/14 Cleaning economic_monthly.csv")
df = pd.read_csv(f"{INPUT_DIR}/economic_monthly.csv")
df = trim_whitespace(df, "economic_monthly.csv")
df = drop_duplicate_rows(df, "economic_monthly.csv")
# 'month' is like "2020-01" -> convert to a real date (first day of month)
df["month"] = pd.to_datetime(df["month"], format="%Y-%m", errors="coerce")
df = report_missing(df, "economic_monthly.csv")
df.to_csv(f"{OUTPUT_DIR}/economic_monthly.csv", index=False)
log("  -> saved cleaned/economic_monthly.csv")

# ---------------------------------------------------------------
# 5. expenses.csv
# ---------------------------------------------------------------
section("5/14 Cleaning expenses.csv")
df = pd.read_csv(f"{INPUT_DIR}/expenses.csv")
df = trim_whitespace(df, "expenses.csv")
df = drop_duplicate_rows(df, "expenses.csv")
df = drop_duplicate_ids(df, "expenses.csv", "expense_id")
df = parse_dates(df, "expenses.csv", ["date"])
df = report_missing(df, "expenses.csv")
df.to_csv(f"{OUTPUT_DIR}/expenses.csv", index=False)
log("  -> saved cleaned/expenses.csv")

# ---------------------------------------------------------------
# 6. infrastructure.csv
# ---------------------------------------------------------------
section("6/14 Cleaning infrastructure.csv")
df = pd.read_csv(f"{INPUT_DIR}/infrastructure.csv")
df = trim_whitespace(df, "infrastructure.csv")
df = drop_duplicate_rows(df, "infrastructure.csv")
df = drop_duplicate_ids(df, "infrastructure.csv", "infrastructure_id")
df = parse_dates(df, "infrastructure.csv", ["expected_completion"])
df = report_missing(df, "infrastructure.csv")
df.to_csv(f"{OUTPUT_DIR}/infrastructure.csv", index=False)
log("  -> saved cleaned/infrastructure.csv")

# ---------------------------------------------------------------
# 7. listing_history.csv
# ---------------------------------------------------------------
section("7/14 Cleaning listing_history.csv")
df = pd.read_csv(f"{INPUT_DIR}/listing_history.csv")
df = trim_whitespace(df, "listing_history.csv")
df = drop_duplicate_rows(df, "listing_history.csv")
df = drop_duplicate_ids(df, "listing_history.csv", "listing_id")
df = parse_dates(df, "listing_history.csv", ["listing_date"])
df = flag_price_outliers(df, "listing_history.csv", "asking_price")
df = report_missing(df, "listing_history.csv")
df.to_csv(f"{OUTPUT_DIR}/listing_history.csv", index=False)
log("  -> saved cleaned/listing_history.csv")

# ---------------------------------------------------------------
# 8. localities.csv
# ---------------------------------------------------------------
section("8/14 Cleaning localities.csv")
df = pd.read_csv(f"{INPUT_DIR}/localities.csv")
df = trim_whitespace(df, "localities.csv")
df = drop_duplicate_rows(df, "localities.csv")
df = drop_duplicate_ids(df, "localities.csv", "locality_id")
df = report_missing(df, "localities.csv")
df.to_csv(f"{OUTPUT_DIR}/localities.csv", index=False)
log("  -> saved cleaned/localities.csv")

# ---------------------------------------------------------------
# 9. market_monthly.csv
# ---------------------------------------------------------------
section("9/14 Cleaning market_monthly.csv")
df = pd.read_csv(f"{INPUT_DIR}/market_monthly.csv")
df = trim_whitespace(df, "market_monthly.csv")
df = drop_duplicate_rows(df, "market_monthly.csv")
# Same locality repeats every month on purpose (it's a time series),
# so we do NOT drop duplicate locality_id here -- that would be wrong.
# Instead we check duplicate (locality_id + month) combos, which SHOULD be unique.
before = len(df)
df = df.drop_duplicates(subset=["locality_id", "month"], keep="first")
removed = before - len(df)
if removed:
    log(f"  - market_monthly.csv: removed {removed} duplicate (locality_id, month) row(s)")
df["month"] = pd.to_datetime(df["month"], format="%Y-%m", errors="coerce")
df = flag_price_outliers(df, "market_monthly.csv", "average_price_sqft")
df = report_missing(df, "market_monthly.csv")
df.to_csv(f"{OUTPUT_DIR}/market_monthly.csv", index=False)
log("  -> saved cleaned/market_monthly.csv")

# ---------------------------------------------------------------
# 10. projects.csv
# ---------------------------------------------------------------
section("10/14 Cleaning projects.csv")
df = pd.read_csv(f"{INPUT_DIR}/projects.csv")
df = trim_whitespace(df, "projects.csv")
df = drop_duplicate_rows(df, "projects.csv")
df = drop_duplicate_ids(df, "projects.csv", "project_id")
df = parse_dates(df, "projects.csv", ["launch_date", "completion_date"])
# Logical check: units_sold + units_available should equal total_units
mismatch = (df["units_sold"] + df["units_available"]) != df["total_units"]
if mismatch.sum():
    log(f"  - projects.csv: {mismatch.sum()} row(s) where units_sold + "
        f"units_available != total_units (left as-is, needs source review)")
df = report_missing(df, "projects.csv")
df.to_csv(f"{OUTPUT_DIR}/projects.csv", index=False)
log("  -> saved cleaned/projects.csv")

# ---------------------------------------------------------------
# 11. properties.csv
# ---------------------------------------------------------------
section("11/14 Cleaning properties.csv")
df = pd.read_csv(f"{INPUT_DIR}/properties.csv")
df = trim_whitespace(df, "properties.csv")
df = drop_duplicate_rows(df, "properties.csv")
df = drop_duplicate_ids(df, "properties.csv", "property_id")

# LOGICAL ERROR FIX: a property's floor number cannot be greater than
# the building's total number of floors. This is physically impossible,
# so we cap 'floor' at 'total_floors' instead of deleting the row
# (deleting would lose all the other good data in that row).
bad_floor = df["floor"] > df["total_floors"]
n_bad = bad_floor.sum()
if n_bad:
    df.loc[bad_floor, "floor"] = df.loc[bad_floor, "total_floors"]
    log(f"  - properties.csv: fixed {n_bad} row(s) where floor number was "
        f"higher than the building's total floors (capped floor = total_floors)")

# monthly_rent is missing for 160 properties. This is NOT a data-entry
# mistake -- it simply means that property is not currently listed for
# rent. So we do NOT invent a rent value. We only add a clear flag
# column so it's obvious in analysis.
df["is_for_rent"] = df["monthly_rent"].notna()
log(f"  - properties.csv: added 'is_for_rent' flag column "
    f"({df['is_for_rent'].sum()} for-rent, {(~df['is_for_rent']).sum()} not-for-rent) "
    f"instead of guessing a missing rent value")

df = flag_price_outliers(df, "properties.csv", "asking_price")
df = report_missing(df, "properties.csv")
df.to_csv(f"{OUTPUT_DIR}/properties.csv", index=False)
log("  -> saved cleaned/properties.csv")

# ---------------------------------------------------------------
# 12. property_events.csv
# ---------------------------------------------------------------
section("12/14 Cleaning property_events.csv")
df = pd.read_csv(f"{INPUT_DIR}/property_events.csv")
df = trim_whitespace(df, "property_events.csv")
df = drop_duplicate_rows(df, "property_events.csv")
df = drop_duplicate_ids(df, "property_events.csv", "event_id")
df = parse_dates(df, "property_events.csv", ["event_date"])
# event_value should be a score between 0 and 1
out_of_range = (df["event_value"] < 0) | (df["event_value"] > 1)
if out_of_range.sum():
    log(f"  - property_events.csv: {out_of_range.sum()} row(s) with "
        f"event_value outside expected 0-1 range (flagged, not changed)")
df = report_missing(df, "property_events.csv")
df.to_csv(f"{OUTPUT_DIR}/property_events.csv", index=False)
log("  -> saved cleaned/property_events.csv")

# ---------------------------------------------------------------
# 13. rentals.csv
# ---------------------------------------------------------------
section("13/14 Cleaning rentals.csv")
df = pd.read_csv(f"{INPUT_DIR}/rentals.csv")
df = trim_whitespace(df, "rentals.csv")
df = drop_duplicate_rows(df, "rentals.csv")
df = drop_duplicate_ids(df, "rentals.csv", "rental_id")
df = parse_dates(df, "rentals.csv", ["rental_date"])
df = flag_price_outliers(df, "rentals.csv", "monthly_rent")
df = report_missing(df, "rentals.csv")
df.to_csv(f"{OUTPUT_DIR}/rentals.csv", index=False)
log("  -> saved cleaned/rentals.csv")

# ---------------------------------------------------------------
# 14. transactions.csv
# ---------------------------------------------------------------
section("14/14 Cleaning transactions.csv")
df = pd.read_csv(f"{INPUT_DIR}/transactions.csv")
df = trim_whitespace(df, "transactions.csv")
df = drop_duplicate_rows(df, "transactions.csv")
df = drop_duplicate_ids(df, "transactions.csv", "transaction_id")
df = parse_dates(df, "transactions.csv", ["transaction_date"])
df = flag_price_outliers(df, "transactions.csv", "transaction_price")
df = report_missing(df, "transactions.csv")
df.to_csv(f"{OUTPUT_DIR}/transactions.csv", index=False)
log("  -> saved cleaned/transactions.csv")

# =================================================================
# FINAL RE-CHECK (recheck everything after cleaning, as requested)
# =================================================================
section("FINAL RE-CHECK OF ALL CLEANED FILES")
files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".csv")]
all_good = True
for f in sorted(files):
    cdf = pd.read_csv(f"{OUTPUT_DIR}/{f}")
    dup_rows = cdf.duplicated().sum()
    log(f"  - {f}: {len(cdf)} rows x {len(cdf.columns)} cols | "
        f"duplicate rows = {dup_rows}")
    if dup_rows > 0:
        all_good = False

if all_good:
    log("\nRECHECK RESULT: PASS - no duplicate rows remain in any file.")
else:
    log("\nRECHECK RESULT: Please review flagged duplicates above.")

# =================================================================
# CROSS-FILE REFERENTIAL INTEGRITY RECHECK
# (make sure every foreign key still correctly points to a real row)
# =================================================================
section("RELATIONSHIP RE-CHECK (foreign keys)")
cities = pd.read_csv(f"{OUTPUT_DIR}/cities.csv")
localities = pd.read_csv(f"{OUTPUT_DIR}/localities.csv")
developers = pd.read_csv(f"{OUTPUT_DIR}/developers.csv")
projects = pd.read_csv(f"{OUTPUT_DIR}/projects.csv")
properties = pd.read_csv(f"{OUTPUT_DIR}/properties.csv")

checks = [
    ("localities.city_id -> cities", localities["city_id"], cities["city_id"]),
    ("projects.developer_id -> developers", projects["developer_id"], developers["developer_id"]),
    ("projects.locality_id -> localities", projects["locality_id"], localities["locality_id"]),
    ("properties.project_id -> projects", properties["project_id"], projects["project_id"]),
]
for label, child, parent in checks:
    orphans = (~child.isin(parent)).sum()
    status = "OK" if orphans == 0 else f"{orphans} BROKEN LINK(S)"
    log(f"  - {label}: {status}")

# Save full report to a text file
with open("cleaning_report.txt", "w") as f:
    f.write("\n".join(report_lines))

section("DONE")
log(f"Cleaned files saved in: {OUTPUT_DIR}/")
log("Full report saved as: cleaning_report.txt")
