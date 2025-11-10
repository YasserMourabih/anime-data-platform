import streamlit as st
import pandas as pd
import sqlalchemy
import os
from sklearn.metrics.pairwise import cosine_similarity, linear_kernel
from sklearn.feature_extraction.text import TfidfVectorizer
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
def load_data_v2():
    engine = get_db_engine()
    df_anime = pd.read_sql("SELECT * FROM view_anime_basic", engine)
    df_genres = pd.read_sql("SELECT anime_id, genre FROM view_anime_genres", engine)
    df_tags = pd.read_sql("SELECT anime_id, tag FROM view_anime_tags", engine) 

    # 1. Préparer les genres
    df_genres = df_genres.rename(columns={'genre': 'feature_value'})

    # 2. Préparer les tags
    df_tags = df_tags.rename(columns={'tag': 'feature_value'})

    # 3. Combiner genres et tags
    df_features = pd.concat([
        df_genres[['anime_id', 'feature_value']],
        df_tags[['anime_id', 'feature_value']]
    ], ignore_index=True)

    # 4. Créer la "soupe" de features par anime
    anime_soup = df_features.groupby('anime_id')['feature_value'].apply(
        lambda x: ' '.join(x.astype(str))
    ).reset_index()
    anime_soup.columns = ['anime_id', 'soup']

    # 5. Fusionner avec les titres
    df_final = pd.merge(df_anime[['anime_id', 'title']], anime_soup, on='anime_id', how='left')
    df_final['soup'] = df_final['soup'].fillna('')

    # 6. Appliquer TF-IDF
    tfidf = TfidfVectorizer(stop_words='english', min_df=3, max_features=1000)
    tfidf_matrix = tfidf.fit_transform(df_final['soup'])

    logger.info(f"Taille matrice TF-IDF : {tfidf_matrix.shape}")

    # 7. Calcul de similarité
    similarity_matrix = linear_kernel(tfidf_matrix, tfidf_matrix)

    # 8. Créer un index pour retrouver les animes par titre
    indices = pd.Series(df_final.index, index=df_final['title']).drop_duplicates()

    return df_final, indices, similarity_matrix
    
# --- 2. LOGIQUE DE RECOMMANDATION ---
def get_recommendations(anime_title, df_anime, indices, similarity_matrix, top_k=10):
    """
    Recommande les K animes les plus similaires
    
    Args:
        anime_title (str): Titre de l'anime de référence
        df_anime (pd.DataFrame): DataFrame avec les animes
        indices (pd.Series): Mapping titre -> index
        similarity_matrix (np.ndarray): Matrice de similarité
        top_k (int): Nombre de recommandations
        
    Returns:
        pd.Series: Top K animes similaires avec leurs scores
    """
    # Vérifier que l'anime existe
    if anime_title not in indices:
        logger.warning(f"Anime '{anime_title}' not found in the dataset.")
        return None

    # Trouver l'index de l'anime
    idx = indices[anime_title]

    # Récupérer les scores de similarité pour cet anime
    sim_scores = list(enumerate(similarity_matrix[idx]))

    # Trier par score décroissant
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)

    # Exclure l'anime lui-même (premier résultat)
    sim_scores = sim_scores[1:]

    # Filtrage anti-doublons
    final_recommendations = []
    seen_franchises = set()
    source_root = anime_title[:10].lower()
    seen_franchises.add(source_root)

    for idx, score in sim_scores:
        title = df_anime.iloc[idx]['title']
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
        df_anime, indices, sim_matrix = load_data_v2()
    
    st.success(f"✅ {len(df_anime)} animes disponibles")
    
    # Liste déroulante pour choisir l'anime source
    all_titles = sorted(indices.index.tolist())
    selected_anime = st.selectbox("Tu as aimé quel anime ?", all_titles)

    if st.button("🎯 Trouver des recommandations"):
        recos = get_recommendations(selected_anime, df_anime, indices, sim_matrix, top_k=10)

        if recos is not None and not recos.empty:
            st.success(f"Si tu as aimé **{selected_anime}**, tu devrais essayer :")
            for i, (title, score) in enumerate(recos.items(), 1):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{i}. {title}**")
                with col2:
                    st.write(f"{score:.2%}")
                st.progress(min(int(score * 100), 100))
                st.divider()
        else:
            st.warning("Pas de recommandations trouvées.")

except Exception as e:
    st.error(f"❌ Erreur : {e}")
    logger.error(f"Streamlit error: {e}", exc_info=True)