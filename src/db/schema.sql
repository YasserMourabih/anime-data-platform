-- src/db/schema.sql

-- Cleaning existing tables if they exist
DROP TABLE IF EXISTS raw_anilist;
DROP TABLE IF EXISTS raw_anilist_json;

-- ETL Approach: Storing extracted fields directly
CREATE TABLE IF NOT EXISTS raw_anilist (
    anime_id INTEGER PRIMARY KEY,
    title_romaji TEXT,
    title_english TEXT,
    average_score INTEGER,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);