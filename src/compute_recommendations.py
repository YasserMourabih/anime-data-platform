import pandas as pd
import os
import re
import psycopg2
from psycopg2.extras import execute_batch
from pgvector.psycopg2 import register_vector  # Outil pour insérer les vecteurs
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
    
    def log(msg, level="info"):
        if logger:
            if level == "info": logger.info(msg)
            elif level == "error": logger.error(msg)
        else:
            print(msg)

    log("🧠 Démarrage du pipeline d'embeddings enrichis...")

    # 1. Chargement du Modèle
    log(f"Chargement du modèle : {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)

    # 2. Connexion DB
    db_url = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}?sslmode=require"
    engine = sqlalchemy.create_engine(db_url)
    
# --- 3. Chargement des Données ---
    log("⏳ Chargement des données enrichies (Animes + Studios + Genres + Tags)...")
    
    # A. Les Animes + Studio (via extraction JSON directe pour faire simple)
    # On extrait le nom du studio directement du JSONB
    query_anime = """
    SELECT 
        anime_id, 
        title, 
        description,
        raw_data->'studios'->'nodes'->0->>'name' as studio -- On prend le 1er studio principal
    FROM view_anime_basic
    WHERE description IS NOT NULL AND description != ''
      AND score > 60
    """
    df_anime = pd.read_sql(query_anime, engine)
    
    # B. Les Genres et Tags (Filtrés par RANK !)
    anime_ids_tuple = tuple(df_anime['anime_id'].tolist())
    
    # On charge les tags, mais on récupère aussi leur RANK
    # (Assure-toi que ta vue view_anime_tags a bien la colonne 'rank', sinon utilise raw_anilist_json)
    # Si ta vue n'a pas rank, on fait sans pour l'instant, mais c'est mieux avec.
    df_tags = pd.read_sql(f"SELECT anime_id, tag FROM view_anime_tags WHERE anime_id IN {anime_ids_tuple}", engine)
    
    df_genres = pd.read_sql(f"SELECT anime_id, genre FROM view_anime_genres WHERE anime_id IN {anime_ids_tuple}", engine)

    log(f"✅ {len(df_anime)} animes chargés.")

    # 4. Préparation du "Super Texte" Optimisé
    log("🍳 Création du texte enrichi (Stratégie V3 : Studio + Répétition)...")
    
    # Agglomération des genres
    genres_per_anime = df_genres.groupby('anime_id')['genre'].apply(lambda x: ' '.join(x)).reset_index()
    
    # Agglomération des tags (Tu pourrais filtrer ici si tu avais le rank dans le DF)
    tags_per_anime = df_tags.groupby('anime_id')['tag'].apply(lambda x: ' '.join(x)).reset_index()
    
    # Fusion
    df_final = pd.merge(df_anime, genres_per_anime, on='anime_id', how='left')
    df_final = pd.merge(df_final, tags_per_anime, on='anime_id', how='left')
    df_final = df_final.fillna('')
    
    # Nettoyage description
    df_final['description'] = df_final['description'].apply(clean_html)
    
    # --- LA FORMULE MAGIQUE ---
    # On construit une phrase structurée qui "guide" le modèle
    def create_prompt(row):
        # 1. Le Titre (Répété pour l'ancrage)
        text = f"Anime: {row['title']}. {row['title']}. "
        
        # 2. Le Studio (Contexte visuel/style)
        if row['studio']:
            text += f"Studio: {row['studio']}. "
            
        # 3. Les Genres (Fondamentaux)
        text += f"Genre: {row['genre']}. "
        
        # 4. Les Tags (Détails, mots-clés)
        text += f"Themes: {row['tag']}. "
        
        # 5. Le Synopsis (L'histoire)
        text += f"Story: {row['description']}"
        return text

    df_final['text_to_embed'] = df_final.apply(create_prompt, axis=1)
        
    # On coupe si c'est trop long (les modèles ont souvent une limite, ex: 256 tokens)
    # Mais all-MiniLM gère bien la troncation auto.

    sentences_to_encode = df_final['text_to_embed'].tolist()
    anime_ids = df_final['anime_id'].tolist()
    anime_titles = df_final['title'].tolist()

    # 5. Calcul des Embeddings
    log("🤖 Calcul des vecteurs sur le texte enrichi...")
    embeddings = model.encode(sentences_to_encode, show_progress_bar=True, batch_size=64)
    
    # 6. Insertion dans Neon (pgvector)
    log("💾 Mise à jour de la base vectorielle...")
    conn = psycopg2.connect(db_url)
    register_vector(conn)
    cur = conn.cursor()
    
    data_to_insert = list(zip(anime_ids, anime_titles, embeddings))
    
    query_upsert = """
    INSERT INTO anime_embeddings (anime_id, title, embedding)
    VALUES (%s, %s, %s)
    ON CONFLICT (anime_id) DO UPDATE
    SET title = EXCLUDED.title,
        embedding = EXCLUDED.embedding;
    """
    
    execute_batch(cur, query_upsert, data_to_insert, page_size=500)
    
    conn.commit()
    cur.close()
    conn.close()

    log("🎉 Base vectorielle enrichie et mise à jour !")
    
    return {
        "animes_processed": len(data_to_insert),
        "features_used": "Title + Genres + Tags + Description"
    }