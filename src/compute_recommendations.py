import pandas as pd
import os
import re
import psycopg2
from pgvector.psycopg2 import register_vector # Outil pour insérer les vecteurs
from sentence_transformers import SentenceTransformer # Le modèle d'IA
import sqlalchemy
from dotenv import load_dotenv

load_dotenv()

# --- MODÈLE D'IA ---
# On choisit un modèle "standard" : rapide, performant, et 384 dimensions
# (la taille que tu as définie dans ta table SQL)
MODEL_NAME = 'all-MiniLM-L6-v2' 

def clean_html(raw_html):
    """Nettoie les balises HTML d'une chaîne de caractères."""
    if not raw_html:
        return ''
    cleanr = re.compile('<.*?>')
    text = re.sub(cleanr, '', raw_html)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def compute_and_load_embeddings(logger=None) -> dict:
    """
    Calcule les embeddings sémantiques des synopsis et les charge dans la BDD Neon.
    Remplace l'ancienne logique TF-IDF/Parquet.
    """
    
    def log(msg, level="info"):
        if logger:
            if level == "info": logger.info(msg)
            elif level == "error": logger.error(msg)
        else:
            print(msg)

    log("🧠 Démarrage du pipeline d'embeddings sémantiques...")

    # --- 1. Chargement du Modèle d'IA ---
    log(f"Chargement du modèle Hugging Face : {MODEL_NAME}...")
    # La première fois, cela va télécharger le modèle (plusieurs Mo)
    model = SentenceTransformer(MODEL_NAME)
    log("✅ Modèle chargé en mémoire.")

    # --- 2. Chargement des Données (Synopsis) ---
    log("⏳ Chargement des synopsis depuis Neon...")
    db_url = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}?sslmode=require"
    engine = sqlalchemy.create_engine(db_url)
    
    # Nouveau (filtre sur la description ET le score)
    query = """
    SELECT anime_id, title, description
    FROM view_anime_basic
    WHERE description IS NOT NULL AND description != ''
      AND score > 60 ORDER BY score DESC LIMIT 5000
    """
    df_anime = pd.read_sql(query, engine)

    if df_anime.empty:
        log("⚠️ Aucune description trouvée. Arrêt.")
        return {"animes_processed": 0}

    log(f"✅ {len(df_anime)} animes avec synopsis à traiter.")
    
    # Nettoyage
    df_anime['description_clean'] = df_anime['description'].apply(clean_html)
    
    # Préparer les données pour l'IA
    anime_ids = df_anime['anime_id'].tolist()
    anime_titles = df_anime['title'].tolist()
    # Le modèle a besoin d'une simple liste de phrases
    sentences_to_encode = df_anime['description_clean'].tolist()

    # --- 3. Calcul des Embeddings (Le "gros" travail) ---
    log("🤖 Calcul des embeddings (vecteurs)...")
    # show_progress_bar=True est super pour voir l'avancement
    embeddings = model.encode(sentences_to_encode, show_progress_bar=True, batch_size=64)
    log(f"✅ {len(embeddings)} vecteurs générés (Dimension: {embeddings.shape[1]})")

    # --- 4. Connexion BDD (avec pgvector) ---
    log("💾 Connexion à Neon avec le pilote pgvector...")
    # On utilise psycopg2 directement, c'est mieux pour pgvector
    conn = psycopg2.connect(db_url)
    register_vector(conn) # On apprend au pilote à parler "vecteur"
    cur = conn.cursor()

    # --- 5. Insertion dans la BDD (UPSERT) ---
    log("Chargement des vecteurs dans la table 'anime_embeddings'...")
    
    # On prépare les données pour une insertion en masse
    data_to_insert = list(zip(anime_ids, anime_titles, embeddings))
    
    # Requête d'UPSERT :
    # Si l'anime_id existe, on met à jour l'embedding et le titre
    # Sinon, on l'insère. C'est robuste.
    query_upsert = """
    INSERT INTO anime_embeddings (anime_id, title, embedding)
    VALUES (%s, %s, %s)
    ON CONFLICT (anime_id) DO UPDATE
    SET title = EXCLUDED.title,
        embedding = EXCLUDED.embedding;
    """
    
    # Exécution en masse (beaucoup plus rapide)
    from psycopg2.extras import execute_batch
    execute_batch(cur, query_upsert, data_to_insert, page_size=500)
    
    conn.commit()
    cur.close()
    conn.close()

    log("🎉 Succès ! La base de données vectorielle est à jour.")
    
    return {
        "animes_processed": len(data_to_insert),
        "vector_dimension": embeddings.shape[1],
        "model_used": MODEL_NAME
    }