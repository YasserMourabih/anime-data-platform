import streamlit as st
import pandas as pd
import sqlalchemy
import os
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv
from config import logger

# --- 1. CONFIG & CHARGEMENT ---
st.set_page_config(page_title="Anime Recommender", page_icon="🎬", layout="centered")
load_dotenv()

@st.cache_resource
def get_db_engine():
    url = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
    return sqlalchemy.create_engine(url)

@st.cache_data
def load_data():
    engine = get_db_engine()
    df_anime = pd.read_sql("SELECT * FROM view_anime_basic", engine)
    df_genres = pd.read_sql("SELECT anime_id, genre FROM view_anime_genres", engine)
    
    # Préparation de la matrice
    # how='left' signifie : garde tout ce qu'il y a dans le DataFrame de gauche (df_anime)
    df_merged = pd.merge(df_anime[['anime_id', 'title']], df_genres, on='anime_id', how='left')
    df_merged['genre'] = df_merged['genre'].fillna('Unknown')
    anime_genre_matrix = pd.crosstab(df_merged['title'], df_merged['genre'])
    similarity_matrix = cosine_similarity(anime_genre_matrix)
    
    return df_anime, anime_genre_matrix, similarity_matrix

# --- 2. LOGIQUE DE RECOMMANDATION (CORRIGÉE) ---
def get_recommendations(anime_title, anime_genre_matrix, similarity_matrix, top_k=5):
    """
    Recommande les K animes les plus similaires
    
    Args:
        anime_title (str): Titre de l'anime de référence
        anime_genre_matrix (pd.DataFrame): Matrice anime x genres
        similarity_matrix (np.ndarray): Matrice de similarité
        top_k (int): Nombre de recommandations
        
    Returns:
        pd.Series: Top K animes similaires avec leurs scores
    """
    # Vérifier que l'anime existe
    if anime_title not in anime_genre_matrix.index:
        logger.warning(f"Anime '{anime_title}' not found in the dataset.")
        return None

    # Trouver la position de l'anime
    index = anime_genre_matrix.index.get_loc(anime_title)

    # Récupérer les scores de similarité
    sim_scores = pd.Series(
        similarity_matrix[index], 
        index=anime_genre_matrix.index
    )

    # Trier par ordre décroissant
    sim_scores = sim_scores.sort_values(ascending=False)

    # Exclure l'anime lui-même
    sim_scores = sim_scores.drop(anime_title)
    
    # Filtrage anti-doublons
    final_recommendations = []
    seen_franchises = set()
    source_root = anime_title[:10].lower()
    seen_franchises.add(source_root)

    for title, score in sim_scores.items():
        candidate_root = title[:10].lower()

        if candidate_root in seen_franchises:   
            continue

        final_recommendations.append((title, score))
        seen_franchises.add(candidate_root)
        if len(final_recommendations) >= top_k:
            break
    
    # Convertir en Series
    if final_recommendations:
        titles, scores = zip(*final_recommendations)
        logger.info(f"Extracted {len(titles)} recommendations for '{anime_title}'.")
        return pd.Series(scores, index=titles)
    else:
        logger.warning(f"No recommendations found for '{anime_title}'.")
        return pd.Series(dtype=float)

# --- 3. INTERFACE UTILISATEUR ---
st.title("🎬 Anime Recommender")
st.write("Découvre de nouvelles pépites basées sur tes goûts !")

try:
    with st.spinner("Chargement des données..."):
        df_anime, anime_genre_matrix, sim_matrix = load_data()
    
    st.success(f"✅ {len(anime_genre_matrix)} animes disponibles")
    
    # Liste déroulante pour choisir l'anime source
    all_titles = sorted(anime_genre_matrix.index.tolist())
    selected_anime = st.selectbox("Tu as aimé quel anime ?", all_titles)

    if st.button("🎯 Trouver des recommandations"):
        # ✅ CORRIGÉ : 4 paramètres au lieu de 3
        recos = get_recommendations(selected_anime, anime_genre_matrix, sim_matrix, top_k=10)

        if recos is not None and not recos.empty:
            st.success(f"Si tu as aimé **{selected_anime}**, tu devrais essayer :")
            for i, (title, score) in enumerate(recos.items(), 1):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{i}. {title}**")
                with col2:
                    st.write(f"{score:.2%}")
                st.progress(int(score * 100))
                st.divider()
        else:
            st.warning("Pas de recommandations trouvées.")

except Exception as e:
    st.error(f"❌ Erreur : {e}")
    logger.error(f"Streamlit error: {e}")