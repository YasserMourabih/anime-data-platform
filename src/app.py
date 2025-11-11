# src/app.py (Version optimisée avec Parquet)
import streamlit as st
import pandas as pd
import os

# --- CONFIG ---
st.set_page_config(page_title="Anime Recommender Lite", page_icon="⚡")
PARQUET_PATH = os.path.join(os.path.dirname(__file__), '../data/recommendations.parquet')

@st.cache_data
def load_recommendations():
    """Charge les recommandations depuis le fichier Parquet (ultra-rapide)."""
    df_recos = pd.read_parquet(PARQUET_PATH)
    all_titles = sorted(df_recos['source_title'].unique())
    return df_recos, all_titles

st.title("⚡ Anime Recommender (Parquet Edition)")

# Bouton pour vider le cache
if st.sidebar.button("🔄 Recharger les données"):
    st.cache_data.clear()
    st.rerun()

try:
    df_recos, all_titles = load_recommendations()
    
    st.info(f"📚 {len(all_titles):,} animes disponibles | {len(df_recos):,} recommandations pré-calculées")
    
    selected_anime = st.selectbox("Tu as aimé :", all_titles)
    
    # Afficher le nombre de recommandations disponibles
    if selected_anime:
        nb_recos = len(df_recos[df_recos['source_title'] == selected_anime])
        st.caption(f"{nb_recos} recommandations disponibles")

    if st.button("🔍 Trouver des recommandations"):
        if selected_anime:
            # Filtre Pandas ultra-rapide
            recommendations = df_recos[df_recos['source_title'] == selected_anime].sort_values('score', ascending=False)
            
            if not recommendations.empty:
                st.success(f"**Recommandations pour {selected_anime}** ({len(recommendations)} trouvées) :")
                
                for i, row in enumerate(recommendations.head(10).itertuples(), 1):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**{i}. {row.reco_title}**")
                    with col2:
                        st.write(f"🎯 {int(row.score*100)}%")
                    st.progress(row.score)
            else:
                st.warning(f"⚠️ Aucune recommandation trouvée pour **{selected_anime}**")

except FileNotFoundError:
    st.error("⚠️ Fichier de recommandations introuvable. Assurez-vous d'avoir lancé le script de calcul.")
except Exception as e:
    st.error(f"❌ Erreur lors du chargement des recommandations : {e}")