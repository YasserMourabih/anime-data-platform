-- Vue principale : animes "à plat"
CREATE OR REPLACE VIEW view_anime_basic AS
SELECT
    anime_id,
    raw_data->'title'->>'romaji' AS title,
    raw_data->>'description' AS description,  -- Synopsis de l'anime
    (raw_data->>'averageScore')::INTEGER AS score,
    (raw_data->>'popularity')::INTEGER AS popularity,  -- Popularité pour trier
    (raw_data->>'episodes')::INTEGER AS episodes,
    raw_data->>'format' AS format,
    raw_data->>'status' AS status,
    raw_data->'coverImage'->>'large' AS cover_image,  -- Image de couverture
    -- On extrait l'année de début si disponible
    (raw_data->'startDate'->>'year')::INTEGER AS start_year,
    raw_data->'genres' AS genres, -- Tableau JSON brut des genres
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

-- Vue pour les studios principaux
CREATE OR REPLACE VIEW view_anime_studios AS
SELECT
    anime_id,
    raw_data->'title'->>'romaji' AS title,
    studio_node->>'name' AS studio_name
FROM raw_anilist_json,
LATERAL jsonb_array_elements(raw_data->'studios'->'nodes') AS studio_node;

-- Vue pour les tags (filtrée pour la qualité)
CREATE OR REPLACE VIEW view_anime_tags AS
SELECT
    anime_id,
    raw_data->'title'->>'romaji' AS title,
    tag_node->>'name' AS tag,
    (tag_node->>'rank')::INTEGER AS rank
FROM raw_anilist_json,
LATERAL jsonb_array_elements(raw_data->'tags') AS tag_node
WHERE (tag_node->>'isMediaSpoiler')::BOOLEAN = false -- On exclut les spoilers
  AND (tag_node->>'rank')::INTEGER >= 60; -- On ne garde que les tags pertinents