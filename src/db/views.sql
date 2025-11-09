-- Vue principale : animes "à plat"
CREATE OR REPLACE VIEW view_anime_basic AS
SELECT
    anime_id,
    raw_data->'title'->>'romaji' AS title,
    (raw_data->>'averageScore')::INTEGER AS score,
    (raw_data->>'episodes')::INTEGER AS episodes,
    raw_data->>'format' AS format,
    raw_data->>'status' AS status,
    -- On extrait l'année de début si disponible
    (raw_data->'startDate'->>'year')::INTEGER AS start_year,
    fetched_at
FROM raw_anilist_json;

-- Vue avancée : genres (un anime = plusieurs lignes ici, une par genre)
-- C'est très utile pour analyser la popularité par genre.
CREATE OR REPLACE VIEW view_anime_genres AS
SELECT
    anime_id,
    raw_data->'title'->>'romaji' AS title,
    jsonb_array_elements_text(raw_data->'genres') AS genre
FROM raw_anilist_json;