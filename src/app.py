# src/app.py - Page d'accueil de la plateforme Anime Data
import streamlit as st
from pathlib import Path
from config import logger
import pandas as pd
import os
import sqlalchemy
from dotenv import load_dotenv

load_dotenv()

# --- CONFIG ---
logger.info("🏠 Chargement de la page d'accueil")
st.set_page_config(
    page_title="Anime Data Platform",
    page_icon="🎌",
    layout="wide"
)

# --- LOAD CSS ---
def load_css(file_name):
    """Charge un fichier CSS externe."""
    css_file = Path(__file__).parent / "styles" / file_name
    with open(css_file) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css("global_styles.css")
load_css("home_styles.css")

# L'URL publique de notre fichier Parquet
PARQUET_URL = "https://github.com/YasserMourabih/anime-data-platform/releases/download/v1.0.0-data/recommendations.parquet"

# --- LOAD STATS ---
@st.cache_data(ttl=3600)  # Cache 1 heure
def load_platform_stats():
    """Charge les statistiques dynamiques de la plateforme."""
    stats = {}
    try:
        # --- 1. Stats depuis la BDD (Neon) ---
        # Cette partie était parfaite et ne change pas
        db_url = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}?sslmode=require"
        engine = sqlalchemy.create_engine(db_url)
        
        query_animes = "SELECT COUNT(*) as total FROM view_anime_basic WHERE score > 60"
        df_count = pd.read_sql(query_animes, engine)
        total_animes = int(df_count['total'].iloc[0])
        stats['total_animes'] = f"{total_animes:,}"
        
        # --- 2. Stats depuis le Parquet (Cloud) ---
        # On lit directement depuis l'URL, plus besoin de os.path.exists
        import time
        start = time.time()
        df_recos = pd.read_parquet(PARQUET_URL)
        load_time = (time.time() - start) * 1000  # en ms

        total_recos = len(df_recos)
        stats['total_recos'] = f"{total_recos:,}"
        stats['load_time'] = f"{load_time:.0f}ms" if load_time < 1000 else f"{load_time/1000:.2f}s"
        
        logger.info(f"📊 Stats chargées : {stats['total_animes']} animes, {stats['total_recos']} recommandations")
        return stats

    except Exception as e:
        logger.error(f"❌ Erreur lors du chargement des stats : {e}")
        # Fallback si Neon ou le Parquet est inaccessible
        return {
            'total_animes': "N/A",
            'total_recos': "N/A",
            'load_time': "N/A"
        }

stats = load_platform_stats()

# SVG Icons
RECOMMENDER_ICON = """
<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="12" cy="12" r="10"></circle>
    <circle cx="12" cy="12" r="3"></circle>
    <line x1="12" y1="1" x2="12" y2="5"></line>
    <line x1="12" y1="19" x2="12" y2="23"></line>
    <line x1="4.22" y1="4.22" x2="7.05" y2="7.05"></line>
    <line x1="16.95" y1="16.95" x2="19.78" y2="19.78"></line>
    <line x1="1" y1="12" x2="5" y2="12"></line>
    <line x1="19" y1="12" x2="23" y2="12"></line>
    <line x1="4.22" y1="19.78" x2="7.05" y2="16.95"></line>
    <line x1="16.95" y1="7.05" x2="19.78" y2="4.22"></line>
</svg>
"""

GAME_ICON = """
<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <rect x="2" y="7" width="20" height="15" rx="2" ry="2"></rect>
    <polyline points="17 2 12 7 7 2"></polyline>
    <circle cx="8" cy="14" r="1"></circle>
    <circle cx="16" cy="14" r="1"></circle>
</svg>
"""

# --- HEADER ---
st.markdown('<h1 class="main-title">Anime Data Platform</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Ta plateforme complète pour explorer et découvrir des animes</p>', unsafe_allow_html=True)

# --- PAGES DISPONIBLES ---
st.markdown("## Fonctionnalités disponibles")

col1, col2 = st.columns(2)

with col1:
    st.markdown(f"""
    <div class="page-card">
        <div class="page-card-icon">{RECOMMENDER_ICON}</div>
        <div class="page-card-title">Anime Recommender</div>
        <div class="page-card-desc">Découvre des animes similaires à tes coups de cœur grâce à notre système intelligent</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Lancer le Recommender", key="btn_recommender", use_container_width=True, type="primary"):
        logger.info("📊 Navigation vers Anime Recommender")
        st.switch_page("pages/2_anime_recommender.py")

with col2:
    st.markdown(f"""
    <div class="page-card">
        <div class="page-card-icon">{GAME_ICON}</div>
        <div class="page-card-title">Higher or Lower</div>
        <div class="page-card-desc">Teste tes connaissances et devine quel anime a le meilleur score dans ce jeu addictif</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Jouer à Higher or Lower", key="btn_game", use_container_width=True, type="primary"):
        logger.info("🎮 Navigation vers Higher or Lower")
        st.switch_page("pages/1_higher_lower.py")

# --- À PROPOS ---
st.markdown("---")
st.markdown('<h2 style="text-align: center; margin: 2rem 0;">À propos de la plateforme</h2>', unsafe_allow_html=True)

col_left, col_center1, col_center2, col_right = st.columns([1, 2, 2, 1])
col1 = col_center1
col2 = col_center2

with col1:
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 2rem; border-radius: 15px; color: white; height: 100%;
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);">
        <h3 style="color: white; margin-top: 0;">
            <svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" style="vertical-align: middle; margin-right: 10px;">
                <circle cx="12" cy="12" r="10"></circle>
                <circle cx="12" cy="12" r="3"></circle>
                <line x1="12" y1="1" x2="12" y2="5"></line>
                <line x1="12" y1="19" x2="12" y2="23"></line>
            </svg>
            Anime Recommender
        </h3>
        <ul style="line-height: 1.8; margin: 1rem 0;">
            <li>Algorithme TF-IDF avancé</li>
            <li>Pondération intelligente</li>
            <li>Détection de franchise</li>
            <li>Format Parquet ultra-rapide</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div style="background: linear-gradient(135deg, #f5576c 0%, #f093fb 100%); 
                padding: 2rem; border-radius: 15px; color: white; height: 100%;
                box-shadow: 0 4px 15px rgba(245, 87, 108, 0.3);">
        <h3 style="color: white; margin-top: 0;">
            <svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" style="vertical-align: middle; margin-right: 10px;">
                <rect x="2" y="7" width="20" height="15" rx="2" ry="2"></rect>
                <polyline points="17 2 12 7 7 2"></polyline>
            </svg>
            Higher or Lower
        </h3>
        <ul style="line-height: 1.8; margin: 1rem 0;">
            <li>Interface moderne et animée</li>
            <li>Système de streak et record</li>
            <li>Images floutées pour le défi</li>
            <li>Gameplay addictif</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

# --- FOOTER ---
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #888; padding: 1rem 0; font-size: 0.9rem;">
    <p>Made with Streamlit • PostgreSQL/Neon • Parquet</p>
    <p style="margin-top: 0.5rem;">
        <a href="https://github.com/YasserMourabih/anime-data-platform" target="_blank" style="color: #667eea; text-decoration: none;">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor" style="vertical-align: middle; margin-right: 5px;">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
            </svg>
            Code source
        </a>
    </p>
</div>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    # Logo/Header
    st.markdown("""
    <div class="sidebar-logo">
        <svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path>
            <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path>
        </svg>
        <div class="sidebar-logo-title">Anime Data</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Navigation
    st.markdown('<div class="sidebar-section-title">Navigation</div>', unsafe_allow_html=True)
    st.page_link("app.py", label="Accueil")
    st.page_link("pages/2_anime_recommender.py", label="Recommender")
    st.page_link("pages/1_higher_lower.py", label="Higher or Lower")
    
    st.markdown("---")
    
    # Stats rapides
    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-section-title">Stats</div>', unsafe_allow_html=True)
    st.markdown(f"**Animes** : {stats['total_animes']}")
    st.markdown(f"**Recommandations** : {stats['total_recos']}")
    st.markdown(f"**Performance** : {stats['load_time']}")
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Technologies
    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-section-title">Technologies</div>', unsafe_allow_html=True)
    st.markdown("- Streamlit")
    st.markdown("- PostgreSQL/Neon")
    st.markdown("- Parquet/PyArrow")
    st.markdown("- scikit-learn")
    st.markdown('</div>', unsafe_allow_html=True)