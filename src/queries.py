"""
Requêtes GraphQL et SQL utilisées dans le pipeline d'extraction.
"""

# --- GraphQL Queries ---
ANILIST_FETCH_PAGE_QUERY = '''
query ($page: Int, $perPage: Int) {
  Page (page: $page, perPage: $perPage) {
    pageInfo {
      hasNextPage
      lastPage
    }
    media (type: ANIME, sort: POPULARITY_DESC) {
      id
      title {
        romaji
        english
      }
      startDate {
        year
        month
        day
      }
      averageScore
      genres
      episodes
      format
      status
      description(asHtml: false)
      characters(sort: ROLE, role: MAIN, perPage: 5) { 
        nodes {
          name {
            full
          }
        }
      }
      studios(isMain: true) {
        nodes {
           name
        }
      }
    }
  }
}
'''

# --- SQL Queries ---
ANILIST_UPSERT_ANIME = """
INSERT INTO raw_anilist_json (anime_id, raw_data)
VALUES %s
ON CONFLICT (anime_id) DO UPDATE 
SET raw_data = EXCLUDED.raw_data,
    fetched_at = CURRENT_TIMESTAMP;
"""