import os
import json
import time
import requests
import psycopg2
from psycopg2.extras import execute_values, Json
from dotenv import load_dotenv

# --- CONFIGURATION ---
# Loads the variables from the .env file into the process environment
load_dotenv()

# Retrieving variables from the environment
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
API_URL = os.getenv("ANILIST_API_URL")

# Basic check that the configuration is loaded (good practice for quick debugging)
if not all([DB_HOST, DB_NAME, DB_USER, DB_PASS, API_URL]):
    raise EnvironmentError("❌ Missing environment variables. Check your .env file")

# --- QUERY DEFINITION ---
QUERY = '''
query ($page: Int, $perPage: Int) {
  Page (page: $page, perPage: $perPage) {
    # On demande des métadonnées sur la pagination
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
      averageScore
      # On peux ajouter d'autres champs maintenant (genres, episodes...)
      # comme on stocke en JSONB, ça ne cassera rien !
      genres
      episodes
    }
  }
}
'''

# --- EXTRACTION LOOP ---
current_page = 1
has_next_page = True

print("🚀 Démarrage de l'extraction paginée...")

while (has_next_page) and (current_page <= 10):  # Limite à 10 pages pour les tests
    print(f"📄 Extraction de la page {current_page}...")
    variables = {'page': current_page, 'perPage': 50} # On augmente un peu perPage
    
    try:
        response = requests.post(API_URL, json={'query': QUERY, 'variables': variables}, timeout=10)
        
        # GESTION AVANCÉE DU RATE LIMIT (Optionnel mais recommandé)
        # Si on reçoit une erreur 429 (Too Many Requests), on attend et on réessaie
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            print(f"⚠️ Rate limit atteint. Pause de {retry_after}s...")
            time.sleep(retry_after + 1)
            continue # On recommence la même boucle (même page)

        response.raise_for_status()
        json_data = response.json()

        # 1. Récupérer les données et infos de pagination
        page_data = json_data['data']['Page']['media']
        page_info = json_data['data']['Page']['pageInfo']

        # 2. Transformation (ELT style avec Json wrapper)
        animes_to_insert = [(anime['id'], Json(anime)) for anime in page_data]

        # 3. Chargement immédiat (une page = une transaction)
        # C'est mieux de charger page par page pour ne pas tout perdre si ça plante à la page 50.
        insert_query = """
        INSERT INTO raw_anilist_json (anime_id, raw_data)
        VALUES %s
        ON CONFLICT (anime_id) DO UPDATE 
        SET raw_data = EXCLUDED.raw_data,
            fetched_at = CURRENT_TIMESTAMP;
        """

        with psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS
            ) as conn: # Context manager auto-commits or rollbacks
            with conn.cursor() as cur:
                execute_values(cur, insert_query, animes_to_insert)

        print(f"✅ Page {current_page} insérée ({len(page_data)} animes).")

        # 4. Préparer la suite
        has_next_page = page_info['hasNextPage']
        current_page += 1
        
        # Trèèès important : être gentil avec l'API
        time.sleep(1)


    except Exception as e:
        print(f"❌ Erreur critique à la page {current_page} : {e}")
        # On peut décider de break ou de continuer, pour l'instant on arrête
        break

print("🎉 Extraction terminée !")