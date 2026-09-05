# Data Cleaning Report (RAW -> PROCESSED)

## Step 1 — Load raw CSVs

  - loaded cities.csv: 6 rows
  - loaded localities.csv: 90 rows
  - loaded developers.csv: 40 rows
  - loaded projects.csv: 500 rows
  - loaded properties.csv: 8,000 rows
  - loaded economic_monthly.csv: 72 rows
  - loaded infrastructure.csv: 209 rows
  - loaded market_monthly.csv: 6,480 rows
  - loaded transactions.csv: 20,000 rows
  - loaded rentals.csv: 10,000 rows
  - loaded listing_history.csv: 12,000 rows
  - loaded property_events.csv: 25,000 rows
  - loaded expenses.csv: 8,000 rows
  - loaded documents.csv: 120 rows

## Step 2 — Trim whitespace on text columns

  - done for all tables

## Step 3 — Parse date/month columns

  - projects: parsed ['launch_date', 'completion_date']
  - economic_monthly: parsed ['month']
  - infrastructure: parsed ['expected_completion']
  - market_monthly: parsed ['month']
  - transactions: parsed ['transaction_date']
  - rentals: parsed ['rental_date']
  - listing_history: parsed ['listing_date']
  - property_events: parsed ['event_date']
  - expenses: parsed ['date']
  - documents: parsed ['document_date']

## Step 4 — Remove duplicates

  - (no removals means the table was already clean)

## Step 5 — Referential integrity (drop orphan rows)

  - (no removals means referential integrity was already 100%)

## Step 6 — Missing values

  - properties.monthly_rent: 160 missing values imputed using the median rent for the same (property_type, bedrooms) group -> flagged in 'monthly_rent_was_imputed'
  - documents.embedding: left as NULL on purpose — this column is populated in Phase 5 (RAG), not in Phase 1 cleaning

## Step 7 — Outlier flags (IQR method, rows kept)

  - properties.asking_price: flagged 121 outliers (1.51%) outside [686,750, 23,980,750] -> new column 'asking_price_is_outlier' (rows kept, not deleted)
  - properties.monthly_rent: flagged 109 outliers (1.36%) outside [-2,650, 69,750] -> new column 'monthly_rent_is_outlier' (rows kept, not deleted)
  - transactions.transaction_price: flagged 1668 outliers (8.34%) outside [-10,499,000, 44,371,000] -> new column 'transaction_price_is_outlier' (rows kept, not deleted)
  - rentals.monthly_rent: flagged 133 outliers (1.33%) outside [-3,550, 71,250] -> new column 'monthly_rent_is_outlier' (rows kept, not deleted)

## Step 8 — Clip out-of-range values to their defined bounds

  - (no clipping needed means values were already within bounds)

## Step 9 — Write cleaned CSVs to data/processed/

  - wrote cities.csv: 6 rows, 7 columns
  - wrote localities.csv: 90 rows, 12 columns
  - wrote developers.csv: 40 rows, 7 columns
  - wrote projects.csv: 500 rows, 11 columns
  - wrote properties.csv: 8,000 rows, 16 columns
  - wrote economic_monthly.csv: 72 rows, 7 columns
  - wrote infrastructure.csv: 209 rows, 8 columns
  - wrote market_monthly.csv: 6,480 rows, 10 columns
  - wrote transactions.csv: 20,000 rows, 8 columns
  - wrote rentals.csv: 10,000 rows, 7 columns
  - wrote listing_history.csv: 12,000 rows, 7 columns
  - wrote property_events.csv: 25,000 rows, 6 columns
  - wrote expenses.csv: 8,000 rows, 8 columns
  - wrote documents.csv: 120 rows, 8 columns

## Summary — Before (raw) vs After (processed) row counts

| Table | Raw rows | Processed rows |
|---|---|---|
| cities | 6 | 6 |
| localities | 90 | 90 |
| developers | 40 | 40 |
| projects | 500 | 500 |
| properties | 8,000 | 8,000 |
| economic_monthly | 72 | 72 |
| infrastructure | 209 | 209 |
| market_monthly | 6,480 | 6,480 |
| transactions | 20,000 | 20,000 |
| rentals | 10,000 | 10,000 |
| listing_history | 12,000 | 12,000 |
| property_events | 25,000 | 25,000 |
| expenses | 8,000 | 8,000 |
| documents | 120 | 120 |

Row counts match raw counts wherever no bad rows were found — that's expected here, since Phase 1 validation already confirmed the raw data has 0 duplicates and 0 orphans. The value of this script is that it now PROVES that (rather than assuming it), fixes the one real issue that existed (missing monthly_rent), converts dates to proper datetime types, and adds outlier/imputation flag columns that Phase 3 (EDA) and Phase 4 (ML) can use.