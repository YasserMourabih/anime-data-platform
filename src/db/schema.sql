-- src/db/schema.sql

-- Clean up existing table if exists
DROP TABLE IF EXISTS raw_anilist;
DROP TABLE IF EXISTS raw_anilist_json;

-- ELT (JSONB) Table
CREATE TABLE raw_anilist_json (
    anime_id INT PRIMARY KEY,
    raw_data JSONB,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);