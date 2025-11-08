import os
import json
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

# --- 1. EXTRACTION ---
query = '''
query ($page: Int, $perPage: Int) {
  Page (page: $page, perPage: $perPage) {
    media (type: ANIME, sort: POPULARITY_DESC) {
      id
      title {
        romaji
        english
      }
      averageScore
    }
  }
}
'''
variables = {
    'page': 1, 
    'perPage': 10
    }

print("📡 Calling the AniList API...")
try:
    response = requests.post(API_URL, json={'query': query, 'variables': variables}, timeout=10)
    response.raise_for_status() # Raise an exception if the status is not 200
    data = response.json()['data']['Page']['media']
    print(f"✅ {len(data)} animes retrieved.")
except requests.exceptions.RequestException as e:
    print(f"❌ Error calling API: {e}")
    exit()

# --- 2. TRANSFORMATION (Minimal transformation: JSON wrapping) ---
animes_to_insert = []
for anime in data:
    animes_to_insert.append((
        anime['id'],
        Json(anime)
    ))

# --- 3. LOADING ---
print("💾 Connecting to PostgreSQL...")
try:
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS
    )
    cur = conn.cursor()

    insert_query = """
    INSERT INTO raw_anilist_json (anime_id, raw_data)
    VALUES %s
    ON CONFLICT (anime_id) DO UPDATE 
    SET raw_data = EXCLUDED.raw_data,
        fetched_at = CURRENT_TIMESTAMP;
    """

    execute_values(cur, insert_query, animes_to_insert)
    conn.commit()
    print("✅ JSON data inserted successfully!")

    # Check
    cur.execute("SELECT COUNT(*) FROM raw_anilist;")
    print(f"📊 Total number of animes in database: {cur.fetchone()[0]}")

    cur.close()
    conn.close()

except psycopg2.Error as e:
    print(f"❌ Database error: {e}")