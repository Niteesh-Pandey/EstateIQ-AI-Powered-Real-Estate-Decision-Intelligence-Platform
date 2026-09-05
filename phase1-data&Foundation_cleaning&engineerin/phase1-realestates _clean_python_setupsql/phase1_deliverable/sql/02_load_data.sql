-- Run after 01_schema.sql. Adjust path to wherever the CSVs live on the DB server.
-- psql -U postgres -d real_estate_db -f 02_load_data.sql

\copy core.cities            FROM 'data/raw/cities.csv'            CSV HEADER;
\copy core.localities        FROM 'data/raw/localities.csv'        CSV HEADER;
\copy core.developers        FROM 'data/raw/developers.csv'        CSV HEADER;
\copy core.projects          FROM 'data/raw/projects.csv'          CSV HEADER;
\copy core.properties        FROM 'data/raw/properties.csv'        CSV HEADER;
\copy core.economic_monthly  FROM 'data/raw/economic_monthly.csv'  CSV HEADER;
\copy core.infrastructure    FROM 'data/raw/infrastructure.csv'    CSV HEADER;
\copy core.market_monthly    FROM 'data/raw/market_monthly.csv'    CSV HEADER;
\copy core.transactions      FROM 'data/raw/transactions.csv'      CSV HEADER;
\copy core.rentals           FROM 'data/raw/rentals.csv'           CSV HEADER;
\copy core.listing_history   FROM 'data/raw/listing_history.csv'   CSV HEADER;
\copy core.property_events   FROM 'data/raw/property_events.csv'   CSV HEADER;
\copy core.expenses          FROM 'data/raw/expenses.csv'          CSV HEADER;
-- documents loaded separately after embeddings are generated (see ai/rag/build_index.py)
