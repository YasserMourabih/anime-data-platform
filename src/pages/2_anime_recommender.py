# src/pages/2_anime_recommender.py (Version optimisée avec Parquet)
import streamlit as st
import pandas as pd
import os
from pathlib import Path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import logger

# --- CONFIG ---
st.set_page_config(page_title="Anime Recommender", page_icon="🎯")

logger.info("🎯 Chargement de la page Anime Recommender")

CSV_URL = "https://github.com/YasserMourabih/anime-data-platform/releases/download/v1.0.0-data/recommendations.csv.gz"

# --- LOAD CSS ---
def load_css(file_name):
    """Charge un fichier CSS externe."""
    css_file = Path(__file__).parent.parent / "styles" / file_name
    with open(css_file) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css("global_styles.css")
load_css("recommender_styles.css")

@st.cache_data
def load_recommendations():
    """Charge les recommandations depuis le fichier CSV (ultra-rapide)."""
    logger.info(f"📂 Chargement des recommandations depuis {CSV_URL}")
    df_recos = pd.read_csv(CSV_URL)
    all_titles = sorted(df_recos['source_title'].unique())
    logger.info(f"✅ {len(all_titles)} animes et {len(df_recos)} recommandations chargées")
    return df_recos, all_titles

# --- HEADER ---
st.markdown("""
    <h1 class="main-title">
        <svg class="icon-svg-large" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/>
            <circle cx="12" cy="12" r="6" stroke="currentColor" stroke-width="2"/>
            <circle cx="12" cy="12" r="2" fill="currentColor"/>
        </svg>
        Anime Recommender
    </h1>
""", unsafe_allow_html=True)
st.markdown('<p class="subtitle">Trouve des animes similaires à tes coups de cœur</p>', unsafe_allow_html=True)

try:
    df_recos, all_titles = load_recommendations()
    
    st.info(f"{len(all_titles):,} animes disponibles | {len(df_recos):,} recommandations pré-calculées")
    
    selected_anime = st.selectbox("Tu as aimé", all_titles, index=None, placeholder="Choisis un anime...")
    
    # Afficher le nombre de recommandations disponibles
    if selected_anime:
        nb_recos = len(df_recos[df_recos['source_title'] == selected_anime])
        st.caption(f"{nb_recos} recommandations disponibles pour cet anime")

    if st.button("Trouver des recommandations", type="primary", use_container_width=True):
        if selected_anime:
            logger.info(f"🔍 Recherche de recommandations pour '{selected_anime}'")
            # Filtre Pandas ultra-rapide
            recommendations = df_recos[df_recos['source_title'] == selected_anime].sort_values('score', ascending=False)
            
            if not recommendations.empty:
                logger.info(f"✅ {len(recommendations)} recommandations trouvées pour '{selected_anime}'")
                st.success(f"Recommandations pour **{selected_anime}** ({len(recommendations)} trouvées)")
                
                # Afficher les top 10
                for i, row in enumerate(recommendations.head(10).itertuples(), 1):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"**{i}. {row.reco_title}**")
                    with col2:
                        st.markdown(f'<span class="score-badge">{int(row.score*100)}%</span>', unsafe_allow_html=True)
                    st.progress(row.score)
                
                # Option pour voir plus de recommandations
                if len(recommendations) > 10:
                    with st.expander(f"Voir toutes les {len(recommendations)} recommandations"):
                        for i, row in enumerate(recommendations.iloc[10:].itertuples(), 11):
                            col1, col2 = st.columns([4, 1])
                            with col1:
                                st.write(f"**{i}. {row.reco_title}**")
                            with col2:
                                st.write(f"{int(row.score*100)}%")
            else:
                logger.warning(f"⚠️ Aucune recommandation trouvée pour '{selected_anime}'")
                st.warning(f"Aucune recommandation trouvée pour **{selected_anime}**")
        else:
            st.warning("Veuillez sélectionner un anime d'abord")

except FileNotFoundError:
    logger.error(f"❌ Fichier de recommandations introuvable : {CSV_URL}")
    st.error("Fichier de recommandations introuvable. Assurez-vous d'avoir lancé le script de calcul.")
except Exception as e:
    logger.error(f"❌ Erreur lors du chargement des recommandations : {e}")
    st.error(f"Erreur lors du chargement des recommandations : {e}")

# Sidebar avec informations
with st.sidebar:
    # Logo/Header
    st.markdown("""
    <div class="sidebar-logo">
        <svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <circle cx="12" cy="12" r="6"></circle>
            <circle cx="12" cy="12" r="2"></circle>
        </svg>
        <div class="sidebar-logo-title">Recommender</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Navigation
    st.markdown('<div class="sidebar-section-title">Navigation</div>', unsafe_allow_html=True)
    st.page_link("app.py", label="Accueil")
    st.page_link("pages/2_anime_recommender.py", label="Recommender")
    st.page_link("pages/1_higher_lower.py", label="Higher or Lower")
    
    st.markdown("---")
    
    # Actions
    if st.button("Recharger les données", key="sidebar_reload_btn"):
        logger.info("🔄 Rechargement des données (cache vidé)")
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("---")
    
    # Informations techniques
    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-section-title">Algorithme</div>', unsafe_allow_html=True)
    st.markdown("**TF-IDF** pondéré")
    st.markdown("- Meta (genres/tags)")
    st.markdown("- Synopsis")
    st.markdown("**Détection** de franchise")
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-section-title">Format</div>', unsafe_allow_html=True)
    st.markdown("**Parquet** (Snappy)")
    st.markdown("Utra-rapide")
    st.markdown('</div>', unsafe_allow_html=True)
