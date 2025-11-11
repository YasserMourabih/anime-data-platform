"""
Requêtes GraphQL et SQL utilisées dans le pipeline d'extraction.
"""

# --- GraphQL Queries ---
ANILIST_FETCH_PAGE_QUERY = '''
query ($page: Int, $perPage: Int) {
  Page(page: $page, perPage: $perPage) {
    pageInfo {
      hasNextPage
    }
    media(type: ANIME, sort: POPULARITY_DESC) {
      id
      title {
        romaji
        english
      }
      averageScore
      popularity
      format
      status
      startDate {
        year
        month
      }
      episodes
      genres
      tags {
        name
        rank
        isMediaSpoiler
      }
      description(asHtml: false)
      studios(isMain: true) {
        nodes {
          name
        }
      }
      coverImage {
        large
        color
      }
      relations {
        edges {
          relationType
          node {
            id
            title {
              romaji
            }
          }
        }
      }
      recommendations(sort: RATING_DESC, perPage: 5) {
        nodes {
          mediaRecommendation {
            id
          }
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