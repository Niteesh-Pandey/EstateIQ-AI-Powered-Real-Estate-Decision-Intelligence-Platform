# Data Validation Report

## Row Counts

- **cities**: 6 rows, 7 columns
- **localities**: 90 rows, 12 columns
- **developers**: 40 rows, 7 columns
- **projects**: 500 rows, 11 columns
- **properties**: 8,000 rows, 13 columns
- **economic_monthly**: 72 rows, 7 columns
- **infrastructure**: 209 rows, 8 columns
- **market_monthly**: 6,480 rows, 10 columns
- **transactions**: 20,000 rows, 7 columns
- **rentals**: 10,000 rows, 6 columns
- **listing_history**: 12,000 rows, 7 columns
- **property_events**: 25,000 rows, 6 columns
- **expenses**: 8,000 rows, 8 columns
- **documents**: 120 rows, 8 columns

## Null Check (%)

- **properties**: monthly_rent=2.0%
- **documents**: embedding=100.0%

## Duplicate Primary Keys

- **cities.city_id**: 0 duplicates
- **localities.locality_id**: 0 duplicates
- **developers.developer_id**: 0 duplicates
- **projects.project_id**: 0 duplicates
- **properties.property_id**: 0 duplicates
- **transactions.transaction_id**: 0 duplicates
- **rentals.rental_id**: 0 duplicates
- **listing_history.listing_id**: 0 duplicates
- **property_events.event_id**: 0 duplicates
- **expenses.expense_id**: 0 duplicates
- **documents.document_id**: 0 duplicates

## Referential Integrity

- **localities.city_id -> cities.city_id**: 0 orphan rows
- **projects.developer_id -> developers.developer_id**: 0 orphan rows
- **projects.locality_id -> localities.locality_id**: 0 orphan rows
- **properties.project_id -> projects.project_id**: 0 orphan rows
- **transactions.property_id -> properties.property_id**: 0 orphan rows
- **rentals.property_id -> properties.property_id**: 0 orphan rows
- **listing_history.property_id -> properties.property_id**: 0 orphan rows
- **property_events.property_id -> properties.property_id**: 0 orphan rows
- **expenses.property_id -> properties.property_id**: 0 orphan rows
- **infrastructure.locality_id -> localities.locality_id**: 0 orphan rows
- **market_monthly.locality_id -> localities.locality_id**: 0 orphan rows

## Range / Sanity Checks

- **properties.asking_price** (non-positive asking price): 0 violations
- **properties.area_sqft** (non-positive area): 0 violations
- **transactions.transaction_price** (non-positive transaction price): 0 violations
- **market_monthly.demand_index** (demand index out of [0,100]): 0 violations
- **economic_monthly.interest_rate** (interest rate implausible): 0 violations

## Outlier Scan (properties.asking_price, IQR method)

- Outliers beyond [686,750, 23,980,750]: 121 rows (1.51%)

## Conclusion

Dataset generated with fixed seed=42 (reproducible). Minor injected nulls (~2%) and outliers (~0.5%) are intentional to mimic real-world messiness and to give the cleaning/staging layer something real to do.