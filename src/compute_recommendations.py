import pandas as pd
import json
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
from dotenv import load_dotenv
import sqlalchemy
from config import logger

# --- CONFIG ---
TOP_K_TO_SAVE = 20  # On ne garde que les 50 meilleurs par anime pour économiser de la place
OUTPUT_FILE = 'data/recommendations.json'

load_dotenv()
DB_URL = os.getenv("DATABASE_URL_PROD") # Utilise la PROD pour avoir les dernières données
engine = sqlalchemy.create_engine(DB_URL)

logger.info("⏳ Chargement des données depuis Neon...")
df_anime = pd.read_sql("SELECT anime_id, title FROM view_anime_basic", engine)
df_genres = pd.read_sql("SELECT anime_id, genre FROM view_anime_genres", engine)
df_tags = pd.read_sql("SELECT anime_id, tag FROM view_anime_tags", engine)

logger.info("🍳 Préparation de la soupe TF-IDF...")
# (Même logique que ton notebook : création de la soupe)
df_features = pd.concat([
    df_genres.rename(columns={'genre': 'feature_value'})[['anime_id', 'feature_value']],
    df_tags.rename(columns={'tag': 'feature_value'})[['anime_id', 'feature_value']]
])
anime_soup = df_features.groupby('anime_id')['feature_value'].apply(lambda x: ' '.join(x)).reset_index()
anime_soup.columns = ['anime_id', 'soup']
df_final = pd.merge(df_anime, anime_soup, on='anime_id', how='left').fillna('')

logger.info("🧮 Calcul de la matrice de similarité (ça peut prendre un peu de RAM)...")
tfidf = TfidfVectorizer(stop_words='english', min_df=2)
tfidf_matrix = tfidf.fit_transform(df_final['soup'])
cosine_sim = linear_kernel(tfidf_matrix, tfidf_matrix)

logger.info(f"💾 Extraction des {TOP_K_TO_SAVE} meilleures recos par anime...")
# Dictionnaire final : { "Titre Anime 1": [ ["Reco 1", score], ["Reco 2", score] ... ], ... }
recommendations_dict = {}

for idx, row in df_final.iterrows():
    title = row['title']
    # Récupérer les scores de similarité pour cet anime
    sim_scores = list(enumerate(cosine_sim[idx]))
    # Trier par score décroissant
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
    # Prendre les Top K (en ignorant le premier qui est lui-même)
    sim_scores = sim_scores[1:TOP_K_TO_SAVE+1]
    
    # Formater pour le JSON
    anime_recos = []
    for i, score in sim_scores:
        reco_title = df_final.iloc[i]['title']
        # Petite optimisation : on arrondit le score pour gagner de la place texte
        anime_recos.append([reco_title, round(float(score), 3)])
        
    recommendations_dict[title] = anime_recos

logger.info(f"📦 Sauvegarde dans {OUTPUT_FILE}...")
os.makedirs('data', exist_ok=True)
with open(OUTPUT_FILE, 'w') as f:
    json.dump(recommendations_dict, f)

logger.info("✅ Terminé ! Le fichier JSON est prêt à être déployé.")