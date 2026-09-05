-- Run this FIRST, connected to the default 'postgres' database.
-- psql -U postgres -f sql/00_create_database.sql

DROP DATABASE IF EXISTS real_estate_db;
CREATE DATABASE real_estate_db;

-- Optional dedicated app user (matches .env.example DB_USER/DB_PASSWORD)
DO $$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'real_estate_app') THEN
      CREATE ROLE real_estate_app LOGIN PASSWORD 'change-this-password';
   END IF;
END
$$;

GRANT ALL PRIVILEGES ON DATABASE real_estate_db TO real_estate_app;
