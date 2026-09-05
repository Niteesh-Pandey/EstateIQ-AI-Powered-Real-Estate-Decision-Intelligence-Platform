-- ============================================================
-- Real Estate Intelligence Platform — PostgreSQL Schema
-- Run this on a PostgreSQL 14+ instance.
-- ============================================================
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS ml;
CREATE SCHEMA IF NOT EXISTS ai;

CREATE EXTENSION IF NOT EXISTS vector;  -- pgvector, for RAG embeddings

-- ================= CORE TABLES =================
CREATE TABLE IF NOT EXISTS core.cities (
    city_id INT PRIMARY KEY,
    city_name TEXT NOT NULL,
    state TEXT,
    country TEXT,
    population BIGINT,
    average_income NUMERIC,
    development_score NUMERIC
);

CREATE TABLE IF NOT EXISTS core.localities (
    locality_id INT PRIMARY KEY,
    city_id INT REFERENCES core.cities(city_id),
    locality_name TEXT NOT NULL,
    latitude NUMERIC,
    longitude NUMERIC,
    population_density INT,
    average_income NUMERIC,
    connectivity_score NUMERIC,
    safety_score NUMERIC,
    infrastructure_score NUMERIC,
    development_score NUMERIC,
    commercial_score NUMERIC
);

CREATE TABLE IF NOT EXISTS core.developers (
    developer_id INT PRIMARY KEY,
    developer_name TEXT NOT NULL,
    rating NUMERIC,
    delivery_score NUMERIC,
    quality_score NUMERIC,
    track_record INT,
    market_share NUMERIC
);

CREATE TABLE IF NOT EXISTS core.projects (
    project_id INT PRIMARY KEY,
    developer_id INT REFERENCES core.developers(developer_id),
    locality_id INT REFERENCES core.localities(locality_id),
    project_name TEXT,
    project_type TEXT,
    launch_date DATE,
    completion_date DATE,
    total_units INT,
    units_sold INT,
    units_available INT,
    project_status TEXT
);

CREATE TABLE IF NOT EXISTS core.properties (
    property_id INT PRIMARY KEY,
    project_id INT REFERENCES core.projects(project_id),
    property_type TEXT,
    bedrooms INT,
    bathrooms INT,
    area_sqft NUMERIC,
    floor INT,
    total_floors INT,
    age_years INT,
    parking INT,
    furnishing TEXT,
    asking_price NUMERIC,
    monthly_rent NUMERIC
);

CREATE TABLE IF NOT EXISTS core.transactions (
    transaction_id INT PRIMARY KEY,
    property_id INT REFERENCES core.properties(property_id),
    transaction_date DATE,
    transaction_price NUMERIC,
    price_per_sqft NUMERIC,
    buyer_type TEXT,
    transaction_type TEXT
);

CREATE TABLE IF NOT EXISTS core.rentals (
    rental_id INT PRIMARY KEY,
    property_id INT REFERENCES core.properties(property_id),
    rental_date DATE,
    monthly_rent NUMERIC,
    vacancy_days INT,
    lease_duration INT
);

CREATE TABLE IF NOT EXISTS core.listing_history (
    listing_id INT PRIMARY KEY,
    property_id INT REFERENCES core.properties(property_id),
    listing_date DATE,
    asking_price NUMERIC,
    status TEXT,
    days_on_market INT,
    price_change_pct NUMERIC
);

CREATE TABLE IF NOT EXISTS core.market_monthly (
    locality_id INT REFERENCES core.localities(locality_id),
    month TEXT,
    average_price_sqft NUMERIC,
    median_price_sqft NUMERIC,
    demand_index NUMERIC,
    supply_index NUMERIC,
    units_sold INT,
    available_inventory INT,
    absorption_rate NUMERIC,
    average_days_on_market INT,
    PRIMARY KEY (locality_id, month)
);

CREATE TABLE IF NOT EXISTS core.economic_monthly (
    month TEXT PRIMARY KEY,
    interest_rate NUMERIC,
    mortgage_rate NUMERIC,
    inflation NUMERIC,
    unemployment NUMERIC,
    gdp_growth NUMERIC,
    income_growth NUMERIC
);

CREATE TABLE IF NOT EXISTS core.infrastructure (
    infrastructure_id INT PRIMARY KEY,
    locality_id INT REFERENCES core.localities(locality_id),
    type TEXT,
    latitude NUMERIC,
    longitude NUMERIC,
    distance_from_center NUMERIC,
    expected_completion DATE,
    impact_score NUMERIC
);

CREATE TABLE IF NOT EXISTS core.property_events (
    event_id INT PRIMARY KEY,
    property_id INT REFERENCES core.properties(property_id),
    event_date DATE,
    event_type TEXT,
    source TEXT,
    event_value NUMERIC
);

CREATE TABLE IF NOT EXISTS core.expenses (
    expense_id INT PRIMARY KEY,
    property_id INT REFERENCES core.properties(property_id),
    date DATE,
    property_tax NUMERIC,
    maintenance NUMERIC,
    insurance NUMERIC,
    management_cost NUMERIC,
    renovation_cost NUMERIC
);

CREATE TABLE IF NOT EXISTS ai.documents (
    document_id INT PRIMARY KEY,
    source TEXT,
    document_date DATE,
    city TEXT,
    locality TEXT,
    topic TEXT,
    text TEXT,
    embedding vector(384)  -- adjust dim to your embedding model
);

-- ================= INDEXES =================
CREATE INDEX IF NOT EXISTS idx_properties_project ON core.properties(project_id);
CREATE INDEX IF NOT EXISTS idx_transactions_property ON core.transactions(property_id);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON core.transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_market_locality_month ON core.market_monthly(locality_id, month);
CREATE INDEX IF NOT EXISTS idx_projects_locality ON core.projects(locality_id);
CREATE INDEX IF NOT EXISTS idx_listing_property ON core.listing_history(property_id);

-- ================= AI SAFETY: READ-ONLY ROLE =================
-- Create a dedicated role for the AI/agent layer with SELECT-only access
-- DO $$ BEGIN
--   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ai_readonly') THEN
--     CREATE ROLE ai_readonly LOGIN PASSWORD 'change_me';
--   END IF;
-- END $$;
-- GRANT USAGE ON SCHEMA core, analytics TO ai_readonly;
-- GRANT SELECT ON ALL TABLES IN SCHEMA core, analytics TO ai_readonly;
