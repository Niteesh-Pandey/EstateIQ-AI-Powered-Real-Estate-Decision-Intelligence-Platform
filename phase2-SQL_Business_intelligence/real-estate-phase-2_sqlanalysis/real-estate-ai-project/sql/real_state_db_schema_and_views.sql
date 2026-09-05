-- ============================================================
--  real_state_db — Schema + Data Load + Analytics Views
-- ============================================================


CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS analytics;

SET search_path TO core, public;

-- ---------------------------------------------------------------
-- 1. cities
-- ---------------------------------------------------------------
CREATE TABLE core.cities (
    city_id INT PRIMARY KEY,
    city_name VARCHAR(255),
    state VARCHAR(255),
    country VARCHAR(255),
    population BIGINT,
    average_income BIGINT,
    development_score NUMERIC(5,2)
);

-- ---------------------------------------------------------------
-- 2. developers
-- ---------------------------------------------------------------
CREATE TABLE core.developers (
    developer_id INT PRIMARY KEY,
    developer_name VARCHAR(255),
    rating NUMERIC(3,2),
    delivery_score NUMERIC(5,2),
    quality_score NUMERIC(5,2),
    track_record INT,
    market_share NUMERIC(5,2)
);

-- ---------------------------------------------------------------
-- 3. documents
-- ---------------------------------------------------------------
CREATE TABLE core.documents (
    document_id INT PRIMARY KEY,
    source VARCHAR(255),
    document_date DATE,
    city VARCHAR(255),
    locality VARCHAR(255),
    topic VARCHAR(255),
    text TEXT,
    embedding NUMERIC
);

-- ---------------------------------------------------------------
-- 4. economic_monthly  (month stored as 'YYYY-MM' text in the CSV ->
--    load through a staging table, then convert to a real DATE)
-- ---------------------------------------------------------------
CREATE TABLE core.economic_monthly (
    month DATE,
    interest_rate NUMERIC(5,2),
    mortgage_rate NUMERIC(5,2),
    inflation NUMERIC(5,2),
    unemployment NUMERIC(5,2),
    gdp_growth NUMERIC(5,2),
    income_growth NUMERIC(5,2)
);

CREATE TEMP TABLE stg_economic_monthly (
    month TEXT,
    interest_rate NUMERIC(5,2),
    mortgage_rate NUMERIC(5,2),
    inflation NUMERIC(5,2),
    unemployment NUMERIC(5,2),
    gdp_growth NUMERIC(5,2),
    income_growth NUMERIC(5,2)
);

-- ---------------------------------------------------------------
-- 5. localities
-- ---------------------------------------------------------------
CREATE TABLE core.localities (
    locality_id INT PRIMARY KEY,
    city_id INT REFERENCES core.cities(city_id),
    locality_name VARCHAR(255),
    latitude NUMERIC(10,8),
    longitude NUMERIC(11,8),
    population_density INT,
    average_income BIGINT,
    connectivity_score NUMERIC(5,2),
    safety_score NUMERIC(5,2),
    infrastructure_score NUMERIC(5,2),
    development_score NUMERIC(5,2),
    commercial_score NUMERIC(5,2)
);

-- ---------------------------------------------------------------
-- 6. infrastructure
-- ---------------------------------------------------------------
CREATE TABLE core.infrastructure (
    infrastructure_id INT PRIMARY KEY,
    locality_id INT REFERENCES core.localities(locality_id),
    type VARCHAR(255),
    latitude NUMERIC(10,8),
    longitude NUMERIC(11,8),
    distance_from_center NUMERIC(8,2),
    expected_completion DATE,
    impact_score NUMERIC(5,2)
);

-- ---------------------------------------------------------------
-- 7. market_monthly (same 'YYYY-MM' issue as economic_monthly)
-- ---------------------------------------------------------------
CREATE TABLE core.market_monthly (
    locality_id INT REFERENCES core.localities(locality_id),
    month DATE,
    average_price_sqft NUMERIC(12,2),
    median_price_sqft NUMERIC(12,2),
    demand_index NUMERIC(5,2),
    supply_index NUMERIC(5,2),
    units_sold INT,
    available_inventory INT,
    absorption_rate NUMERIC(5,2),
    average_days_on_market INT
);

CREATE TEMP TABLE stg_market_monthly (
    locality_id INT,
    month TEXT,
    average_price_sqft NUMERIC(12,2),
    median_price_sqft NUMERIC(12,2),
    demand_index NUMERIC(5,2),
    supply_index NUMERIC(5,2),
    units_sold INT,
    available_inventory INT,
    absorption_rate NUMERIC(5,2),
    average_days_on_market INT
);

-- ---------------------------------------------------------------
-- 8. projects
-- ---------------------------------------------------------------
CREATE TABLE core.projects (
    project_id INT PRIMARY KEY,
    developer_id INT REFERENCES core.developers(developer_id),
    locality_id INT REFERENCES core.localities(locality_id),
    project_name VARCHAR(255),
    project_type VARCHAR(100),
    launch_date DATE,
    completion_date DATE,
    total_units INT,
    units_sold INT,
    units_available INT,
    project_status VARCHAR(50)
);

-- ---------------------------------------------------------------
-- 9. properties
-- ---------------------------------------------------------------
CREATE TABLE core.properties (
    property_id INT PRIMARY KEY,
    project_id INT REFERENCES core.projects(project_id),
    property_type VARCHAR(100),
    bedrooms INT,
    bathrooms INT,
    area_sqft INT,
    floor INT,
    total_floors INT,
    age_years INT,
    parking INT,
    furnishing VARCHAR(50),
    asking_price NUMERIC(15,2),
    monthly_rent NUMERIC(12,2),
    monthly_rent_was_imputed BOOLEAN,
    asking_price_is_outlier BOOLEAN,
    monthly_rent_is_outlier BOOLEAN
);

-- ---------------------------------------------------------------
-- 10. property_events
-- ---------------------------------------------------------------
CREATE TABLE core.property_events (
    event_id INT PRIMARY KEY,
    property_id INT REFERENCES core.properties(property_id),
    event_date DATE,
    event_type VARCHAR(100),
    source VARCHAR(255),
    event_value NUMERIC(15,2)
);

-- ---------------------------------------------------------------
-- 11. rentals
-- ---------------------------------------------------------------
CREATE TABLE core.rentals (
    rental_id INT PRIMARY KEY,
    property_id INT REFERENCES core.properties(property_id),
    rental_date DATE,
    monthly_rent NUMERIC(12,2),
    vacancy_days INT,
    lease_duration INT,
    monthly_rent_is_outlier BOOLEAN
);

-- ---------------------------------------------------------------
-- 12. transactions
-- ---------------------------------------------------------------
CREATE TABLE core.transactions (
    transaction_id INT PRIMARY KEY,
    property_id INT REFERENCES core.properties(property_id),
    transaction_date DATE,
    transaction_price NUMERIC(15,2),
    price_per_sqft NUMERIC(12,2),
    buyer_type VARCHAR(100),
    transaction_type VARCHAR(100),
    transaction_price_is_outlier BOOLEAN
);

-- ---------------------------------------------------------------
-- 13. expenses
-- ---------------------------------------------------------------
CREATE TABLE core.expenses (
    expense_id INT PRIMARY KEY,
    property_id INT REFERENCES core.properties(property_id),
    date DATE,
    property_tax NUMERIC(12,2),
    maintenance NUMERIC(12,2),
    insurance NUMERIC(12,2),
    management_cost NUMERIC(12,2),
    renovation_cost NUMERIC(12,2)
);

-- ---------------------------------------------------------------
-- 14. listing_history
-- ---------------------------------------------------------------
CREATE TABLE core.listing_history (
    listing_id INT PRIMARY KEY,
    property_id INT REFERENCES core.properties(property_id),
    listing_date DATE,
    asking_price NUMERIC(15,2),
    status VARCHAR(50),
    days_on_market INT,
    price_change_pct NUMERIC(5,2)
);

-- ================= LOAD DATA (dependency-safe order) =================
\copy core.cities              FROM 'data/processed/cities.csv'              DELIMITER ',' CSV HEADER;
\copy core.developers          FROM 'data/processed/developers.csv'          DELIMITER ',' CSV HEADER;
\copy core.documents           FROM 'data/processed/documents.csv'           DELIMITER ',' CSV HEADER;
\copy core.localities          FROM 'data/processed/localities.csv'          DELIMITER ',' CSV HEADER;
\copy core.infrastructure      FROM 'data/processed/infrastructure.csv'      DELIMITER ',' CSV HEADER;
\copy core.projects            FROM 'data/processed/projects.csv'            DELIMITER ',' CSV HEADER;
\copy core.properties          FROM 'data/processed/properties.csv'          DELIMITER ',' CSV HEADER;
\copy core.property_events     FROM 'data/processed/property_events.csv'     DELIMITER ',' CSV HEADER;
\copy core.rentals             FROM 'data/processed/rentals.csv'             DELIMITER ',' CSV HEADER;
\copy core.transactions        FROM 'data/processed/transactions.csv'        DELIMITER ',' CSV HEADER;
\copy core.expenses            FROM 'data/processed/expenses.csv'            DELIMITER ',' CSV HEADER;
\copy core.listing_history     FROM 'data/processed/listing_history.csv'     DELIMITER ',' CSV HEADER;

\copy stg_economic_monthly     FROM 'data/processed/economic_monthly.csv'    DELIMITER ',' CSV HEADER;
\copy stg_market_monthly       FROM 'data/processed/market_monthly.csv'      DELIMITER ',' CSV HEADER;

INSERT INTO core.economic_monthly
SELECT to_date(month,'YYYY-MM'), interest_rate, mortgage_rate, inflation, unemployment, gdp_growth, income_growth
FROM stg_economic_monthly;

INSERT INTO core.market_monthly
SELECT locality_id, to_date(month,'YYYY-MM'), average_price_sqft, median_price_sqft, demand_index, supply_index,
       units_sold, available_inventory, absorption_rate, average_days_on_market
FROM stg_market_monthly;

-- ================= INDEXES =================
CREATE INDEX IF NOT EXISTS idx_properties_project ON core.properties(project_id);
CREATE INDEX IF NOT EXISTS idx_transactions_property ON core.transactions(property_id);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON core.transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_market_locality_month ON core.market_monthly(locality_id, month);
CREATE INDEX IF NOT EXISTS idx_projects_locality ON core.projects(locality_id);
CREATE INDEX IF NOT EXISTS idx_listing_property ON core.listing_history(property_id);
CREATE INDEX IF NOT EXISTS idx_transactions_property_date ON core.transactions(property_id, transaction_date);
CREATE INDEX IF NOT EXISTS idx_listing_history_property_status ON core.listing_history(property_id, status);
CREATE INDEX IF NOT EXISTS idx_properties_project_type ON core.properties(project_id, property_type);
CREATE INDEX IF NOT EXISTS idx_listing_history_status ON core.listing_history(status);
-- ============================================================
-- PHASE 2 — SQL Analytics Layer (fixed)
-- ============================================================

-- 1. Locality market trend: YoY growth + rolling averages
CREATE OR REPLACE VIEW analytics.v_locality_market_trend AS
WITH m AS (
    SELECT
        locality_id,
        month,
        month AS month_date,
        average_price_sqft,
        median_price_sqft,
        demand_index,
        supply_index,
        demand_index / NULLIF(supply_index, 0) AS demand_supply_ratio,
        units_sold,
        available_inventory,
        absorption_rate,
        average_days_on_market
    FROM core.market_monthly
)
SELECT
    m.*,
    LAG(average_price_sqft, 12) OVER (PARTITION BY locality_id ORDER BY month_date) AS price_sqft_12m_ago,
    ROUND(
      ( (average_price_sqft - LAG(average_price_sqft, 12) OVER (PARTITION BY locality_id ORDER BY month_date))
        / NULLIF(LAG(average_price_sqft, 12) OVER (PARTITION BY locality_id ORDER BY month_date), 0) ) * 100, 2
    ) AS yoy_growth_pct,
    ROUND(
      ( (average_price_sqft - LAG(average_price_sqft, 1) OVER (PARTITION BY locality_id ORDER BY month_date))
        / NULLIF(LAG(average_price_sqft, 1) OVER (PARTITION BY locality_id ORDER BY month_date), 0) ) * 100, 2
    ) AS mom_growth_pct,
    AVG(average_price_sqft) OVER (PARTITION BY locality_id ORDER BY month_date
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS rolling_3m_avg_psf,
    AVG(average_price_sqft) OVER (PARTITION BY locality_id ORDER BY month_date
        ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) AS rolling_12m_avg_psf
FROM m;

-- 2. Locality ranking as of the latest month
CREATE OR REPLACE VIEW analytics.v_locality_ranking AS
SELECT
    l.locality_id,
    l.locality_name,
    c.city_name,
    t.yoy_growth_pct,
    t.demand_supply_ratio,
    t.absorption_rate,
    t.average_days_on_market,
    RANK()       OVER (ORDER BY t.yoy_growth_pct DESC)      AS growth_rank,
    RANK()       OVER (ORDER BY t.demand_supply_ratio DESC) AS demand_rank,
    DENSE_RANK() OVER (ORDER BY t.average_days_on_market ASC) AS liquidity_rank
FROM analytics.v_locality_market_trend t
JOIN core.localities l ON l.locality_id = t.locality_id
JOIN core.cities c ON c.city_id = l.city_id
WHERE t.month_date = (SELECT MAX(month_date) FROM analytics.v_locality_market_trend);

-- 3. Top / bottom 10 movers
CREATE OR REPLACE VIEW analytics.v_top_bottom_localities AS
(SELECT *, 'top_growth' AS bucket FROM analytics.v_locality_ranking ORDER BY growth_rank ASC LIMIT 10)
UNION ALL
(SELECT *, 'bottom_growth' AS bucket FROM analytics.v_locality_ranking ORDER BY growth_rank DESC LIMIT 10);

-- 4. Developer performance
CREATE OR REPLACE VIEW analytics.v_developer_performance AS
SELECT
    d.developer_id,
    d.developer_name,
    d.rating,
    d.delivery_score,
    d.market_share,
    COUNT(p.project_id) AS total_projects,
    SUM(p.total_units) AS total_units,
    SUM(p.units_sold) AS total_units_sold,
    ROUND(SUM(p.units_sold)::NUMERIC / NULLIF(SUM(p.total_units), 0) * 100, 1) AS sales_velocity_pct,
    RANK() OVER (ORDER BY SUM(p.units_sold)::NUMERIC / NULLIF(SUM(p.total_units), 0) DESC) AS velocity_rank
FROM core.developers d
LEFT JOIN core.projects p ON p.developer_id = d.developer_id
GROUP BY d.developer_id, d.developer_name, d.rating, d.delivery_score, d.market_share;

-- 5. Property comparables
CREATE OR REPLACE VIEW analytics.v_property_comparables AS
SELECT
    pr.property_id,
    pj.locality_id,
    pr.property_type,
    pr.bedrooms,
    pr.area_sqft,
    pr.asking_price,
    ROUND(pr.asking_price / NULLIF(pr.area_sqft, 0), 1) AS price_per_sqft,
    AVG(pr.asking_price / NULLIF(pr.area_sqft, 0)) OVER (
        PARTITION BY pj.locality_id, pr.property_type, pr.bedrooms
    ) AS comparable_avg_price_sqft
FROM core.properties pr
JOIN core.projects pj ON pj.project_id = pr.project_id
WHERE pr.asking_price_is_outlier IS NOT TRUE;

-- 6. Fair value & valuation gap
CREATE OR REPLACE VIEW analytics.v_property_valuation_gap AS
SELECT
    c.property_id,
    c.asking_price,
    ROUND(c.comparable_avg_price_sqft * c.area_sqft, -3) AS fair_value_estimate,
    c.asking_price - ROUND(c.comparable_avg_price_sqft * c.area_sqft, -3) AS valuation_gap,
    ROUND( (c.asking_price - c.comparable_avg_price_sqft * c.area_sqft)
           / NULLIF(c.comparable_avg_price_sqft * c.area_sqft, 0) * 100, 2) AS valuation_gap_pct
FROM analytics.v_property_comparables c;

-- 7. Rental yield — per property and rolled up per locality
CREATE OR REPLACE VIEW analytics.v_rental_yield AS
SELECT
    p.property_id,
    pj.locality_id,
    p.asking_price,
    p.monthly_rent,
    p.monthly_rent_was_imputed,
    ROUND((p.monthly_rent * 12) / NULLIF(p.asking_price, 0) * 100, 2) AS gross_rental_yield_pct
FROM core.properties p
JOIN core.projects pj ON pj.project_id = p.project_id
WHERE p.monthly_rent IS NOT NULL AND p.asking_price > 0;

CREATE OR REPLACE VIEW analytics.v_rental_yield_by_locality AS
SELECT
    l.locality_id,
    l.locality_name,
    COUNT(*) AS properties_counted,
    ROUND(AVG(y.gross_rental_yield_pct), 2) AS avg_gross_rental_yield_pct,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY y.gross_rental_yield_pct)::NUMERIC, 2) AS median_gross_rental_yield_pct
FROM analytics.v_rental_yield y
JOIN core.localities l ON l.locality_id = y.locality_id
GROUP BY l.locality_id, l.locality_name;

-- 8. Actual transaction price trend
CREATE OR REPLACE VIEW analytics.v_transaction_price_trend AS
WITH monthly AS (
    SELECT
        pj.locality_id,
        pr.property_type,
        DATE_TRUNC('month', t.transaction_date)::DATE AS txn_month,
        AVG(t.price_per_sqft) AS avg_price_per_sqft,
        COUNT(*) AS txn_count
    FROM core.transactions t
    JOIN core.properties pr ON pr.property_id = t.property_id
    JOIN core.projects pj ON pj.project_id = pr.project_id
    WHERE t.transaction_price_is_outlier IS NOT TRUE
    GROUP BY pj.locality_id, pr.property_type, DATE_TRUNC('month', t.transaction_date)
)
SELECT
    *,
    LAG(avg_price_per_sqft, 1) OVER (PARTITION BY locality_id, property_type ORDER BY txn_month) AS prev_month_avg_psf,
    ROUND(
      (avg_price_per_sqft - LAG(avg_price_per_sqft, 1) OVER (PARTITION BY locality_id, property_type ORDER BY txn_month))
      / NULLIF(LAG(avg_price_per_sqft, 1) OVER (PARTITION BY locality_id, property_type ORDER BY txn_month), 0) * 100, 2
    ) AS mom_price_change_pct,
    AVG(avg_price_per_sqft) OVER (PARTITION BY locality_id, property_type ORDER BY txn_month
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS rolling_3m_avg_psf
FROM monthly;

-- 9. Days-on-market by segment
CREATE OR REPLACE VIEW analytics.v_dom_by_segment AS
SELECT
    pj.locality_id,
    l.locality_name,
    pr.property_type,
    pr.bedrooms,
    COUNT(*) AS listings_counted,
    ROUND(AVG(lh.days_on_market), 1) AS avg_days_on_market,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY lh.days_on_market)::NUMERIC, 1) AS median_days_on_market,
    RANK() OVER (ORDER BY AVG(lh.days_on_market) DESC) AS slowest_segment_rank
FROM core.listing_history lh
JOIN core.properties pr ON pr.property_id = lh.property_id
JOIN core.projects pj ON pj.project_id = pr.project_id
JOIN core.localities l ON l.locality_id = pj.locality_id
WHERE lh.days_on_market IS NOT NULL
GROUP BY pj.locality_id, l.locality_name, pr.property_type, pr.bedrooms;

-- 10. Seasonality
CREATE OR REPLACE VIEW analytics.v_seasonality_transactions AS
SELECT
    EXTRACT(MONTH FROM transaction_date)::INT AS calendar_month,
    COUNT(*) AS txn_count,
    ROUND(AVG(price_per_sqft), 1) AS avg_price_per_sqft,
    ROUND(PERCENT_RANK() OVER (ORDER BY COUNT(*))::NUMERIC, 3) AS activity_percentile
FROM core.transactions
GROUP BY EXTRACT(MONTH FROM transaction_date)
ORDER BY calendar_month;

-- 11. Materialized view for dashboard aggregation
CREATE MATERIALIZED VIEW IF NOT EXISTS analytics.mv_city_month_summary AS
SELECT
    l.city_id,
    m.month,
    AVG(m.average_price_sqft) AS avg_price_sqft,
    AVG(m.demand_index) AS avg_demand,
    AVG(m.supply_index) AS avg_supply,
    SUM(m.units_sold) AS total_units_sold,
    SUM(m.available_inventory) AS total_inventory,
    AVG(m.average_days_on_market) AS avg_dom
FROM core.market_monthly m
JOIN core.localities l ON l.locality_id = m.locality_id
GROUP BY l.city_id, m.month;

-- 12. Demand/Supply trend + market-condition label
--     (FIX: month is already a real DATE after load, so we use it
--      directly instead of TO_DATE(month,'YYYY-MM') which crashed
--      on a DATE input)
CREATE OR REPLACE VIEW analytics.v_demand_supply_trend AS
WITH d AS (
    SELECT
        locality_id,
        month,
        month AS month_date,
        demand_index,
        supply_index,
        ROUND(demand_index / NULLIF(supply_index, 0), 2) AS demand_supply_ratio
    FROM core.market_monthly
)
SELECT
    d.*,
    LAG(demand_index, 12) OVER (PARTITION BY locality_id ORDER BY month_date) AS demand_index_12m_ago,
    ROUND(
      (demand_index - LAG(demand_index, 12) OVER (PARTITION BY locality_id ORDER BY month_date))
      / NULLIF(LAG(demand_index, 12) OVER (PARTITION BY locality_id ORDER BY month_date), 0) * 100, 2
    ) AS demand_yoy_change_pct,
    LAG(supply_index, 12) OVER (PARTITION BY locality_id ORDER BY month_date) AS supply_index_12m_ago,
    ROUND(
      (supply_index - LAG(supply_index, 12) OVER (PARTITION BY locality_id ORDER BY month_date))
      / NULLIF(LAG(supply_index, 12) OVER (PARTITION BY locality_id ORDER BY month_date), 0) * 100, 2
    ) AS supply_yoy_change_pct,
    CASE
        WHEN demand_index / NULLIF(supply_index, 0) >= 1.2 THEN 'Seller''s Market'
        WHEN demand_index / NULLIF(supply_index, 0) <= 0.8 THEN 'Buyer''s Market'
        ELSE 'Balanced Market'
    END AS market_condition
FROM d;

-- 13. Months of Inventory (MOI)  — same TO_DATE fix as above
CREATE OR REPLACE VIEW analytics.v_inventory_months AS
WITH m AS (
    SELECT
        locality_id,
        month,
        month AS month_date,
        available_inventory,
        units_sold
    FROM core.market_monthly
),
m2 AS (
    SELECT
        *,
        AVG(units_sold) OVER (PARTITION BY locality_id ORDER BY month_date
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS avg_monthly_sales_3m
    FROM m
)
SELECT
    locality_id, month, month_date, available_inventory, units_sold, avg_monthly_sales_3m,
    ROUND(available_inventory / NULLIF(avg_monthly_sales_3m, 0), 1) AS months_of_inventory,
    CASE
        WHEN available_inventory / NULLIF(avg_monthly_sales_3m, 0) < 4 THEN 'Seller''s Market'
        WHEN available_inventory / NULLIF(avg_monthly_sales_3m, 0) > 8 THEN 'Buyer''s Market'
        ELSE 'Balanced Market'
    END AS inventory_condition
FROM m2;

-- 14a. Market share by developer (derived from actual units_sold)
CREATE OR REPLACE VIEW analytics.v_developer_market_share AS
WITH dev_units AS (
    SELECT
        d.developer_id,
        d.developer_name,
        SUM(p.units_sold) AS total_units_sold
    FROM core.developers d
    LEFT JOIN core.projects p ON p.developer_id = d.developer_id
    GROUP BY d.developer_id, d.developer_name
)
SELECT
    *,
    ROUND(total_units_sold::NUMERIC / NULLIF(SUM(total_units_sold) OVER (), 0) * 100, 2) AS market_share_pct,
    RANK() OVER (ORDER BY total_units_sold DESC) AS market_share_rank
FROM dev_units;

-- 14b. Market share by locality within its city
CREATE OR REPLACE VIEW analytics.v_locality_market_share AS
WITH loc_txn AS (
    SELECT
        pj.locality_id,
        l.locality_name,
        c.city_id,
        c.city_name,
        COUNT(t.transaction_id) AS total_transactions,
        SUM(t.transaction_price) AS total_transaction_value
    FROM core.transactions t
    JOIN core.properties pr ON pr.property_id = t.property_id
    JOIN core.projects pj ON pj.project_id = pr.project_id
    JOIN core.localities l ON l.locality_id = pj.locality_id
    JOIN core.cities c ON c.city_id = l.city_id
    GROUP BY pj.locality_id, l.locality_name, c.city_id, c.city_name
)
SELECT
    *,
    ROUND(total_transactions::NUMERIC
        / NULLIF(SUM(total_transactions) OVER (PARTITION BY city_id), 0) * 100, 2) AS market_share_pct_within_city
FROM loc_txn;

-- 15a. Price segmentation (quartiles per city)
CREATE OR REPLACE VIEW analytics.v_price_segmentation AS
WITH p AS (
    SELECT
        pr.property_id,
        pj.locality_id,
        l.city_id,
        pr.property_type,
        pr.asking_price,
        ROUND(pr.asking_price / NULLIF(pr.area_sqft, 0), 1) AS price_per_sqft,
        NTILE(4) OVER (PARTITION BY l.city_id ORDER BY pr.asking_price / NULLIF(pr.area_sqft, 0)) AS price_quartile
    FROM core.properties pr
    JOIN core.projects pj ON pj.project_id = pr.project_id
    JOIN core.localities l ON l.locality_id = pj.locality_id
    WHERE pr.asking_price_is_outlier IS NOT TRUE
)
SELECT
    *,
    CASE price_quartile
        WHEN 1 THEN 'Budget'
        WHEN 2 THEN 'Mid-Range'
        WHEN 3 THEN 'Premium'
        WHEN 4 THEN 'Luxury'
    END AS price_segment
FROM p;

-- 15b. Price segmentation — city-level rollup
CREATE OR REPLACE VIEW analytics.v_price_segment_summary AS
SELECT
    city_id,
    price_segment,
    COUNT(*) AS property_count,
    ROUND(AVG(asking_price), 0) AS avg_asking_price,
    ROUND(AVG(price_per_sqft), 1) AS avg_price_per_sqft
FROM analytics.v_price_segmentation
GROUP BY city_id, price_segment;

-- 16. Sales conversion / velocity
CREATE OR REPLACE VIEW analytics.v_sales_conversion_velocity AS
SELECT
    pj.locality_id,
    l.locality_name,
    pr.property_type,
    COUNT(*) AS total_listings,
    COUNT(*) FILTER (WHERE lh.status = 'Sold') AS sold_count,
    ROUND(COUNT(*) FILTER (WHERE lh.status = 'Sold')::NUMERIC
        / NULLIF(COUNT(*), 0) * 100, 2) AS conversion_rate_pct,
    ROUND(AVG(lh.days_on_market) FILTER (WHERE lh.status = 'Sold'), 1) AS avg_days_to_sell,
    RANK() OVER (
        ORDER BY COUNT(*) FILTER (WHERE lh.status = 'Sold')::NUMERIC / NULLIF(COUNT(*), 0) DESC
    ) AS conversion_rank
FROM core.listing_history lh
JOIN core.properties pr ON pr.property_id = lh.property_id
JOIN core.projects pj ON pj.project_id = pr.project_id
JOIN core.localities l ON l.locality_id = pj.locality_id
GROUP BY pj.locality_id, l.locality_name, pr.property_type;

-- 17. Price-vs-Demand descriptive correlation analysis
CREATE OR REPLACE VIEW analytics.v_price_vs_demand_analysis AS
SELECT
    m.locality_id,
    l.locality_name,
    ROUND(CORR(m.demand_index, m.average_price_sqft)::NUMERIC, 3) AS corr_demand_price,
    ROUND(CORR(m.supply_index, m.average_price_sqft)::NUMERIC, 3) AS corr_supply_price,
    ROUND(AVG(m.demand_index), 1) AS avg_demand_index,
    ROUND(AVG(m.average_price_sqft), 1) AS avg_price_sqft,
    CASE
        WHEN CORR(m.demand_index, m.average_price_sqft) >= 0.5 THEN 'Strong positive (demand-driven pricing)'
        WHEN CORR(m.demand_index, m.average_price_sqft) <= -0.5 THEN 'Strong negative (unusual -- investigate)'
        ELSE 'Weak / no clear relationship'
    END AS price_demand_relationship
FROM core.market_monthly m
JOIN core.localities l ON l.locality_id = m.locality_id
GROUP BY m.locality_id, l.locality_name;
