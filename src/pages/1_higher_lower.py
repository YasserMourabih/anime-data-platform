"""
Page Higher or Lower - Devinez si l'anime a un score plus haut ou plus bas !
Version refactorisée avec CSS externe et fonctions modulaires.
"""

import streamlit as st
import pandas as pd
import os
import sqlalchemy
from dotenv import load_dotenv
from pathlib import Path
import sys

load_dotenv()

# Ajouter le dossier parent au path pour importer config
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import logger

logger.info("🎮 Chargement de la page Higher or Lower")


# ============================================================================
# CHARGEMENT DES DONNÉES
# ============================================================================

@st.cache_data
def load_game_data(top_k=500):
    """Charge les animes populaires pour le jeu."""
    logger.info(f"📊 Chargement des {top_k} animes les plus populaires pour le jeu")
    db_url = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}?sslmode=require"
    engine = sqlalchemy.create_engine(db_url)
    
    query = f"""
    SELECT title, score, cover_image
    FROM view_anime_basic 
    WHERE score > 0 
      AND score IS NOT NULL 
      AND popularity IS NOT NULL
      AND cover_image IS NOT NULL
    ORDER BY popularity DESC
    LIMIT {top_k};
    """
    
    df = pd.read_sql(query, engine)
    df = df.drop_duplicates(subset=['title']).reset_index(drop=True)
    logger.info(f"✅ {len(df)} animes chargés pour le jeu")
    return df


# ============================================================================
# GESTION DE L'ÉTAT DU JEU
# ============================================================================

def init_game():
    """Initialise un nouveau jeu."""
    logger.info("🎮 Initialisation d'une nouvelle partie")
    df = st.session_state.df_animes
    st.session_state.score = 0
    st.session_state.streak = 0
    st.session_state.best_streak = 0
    st.session_state.anime_a = df.sample(1).iloc[0]
    st.session_state.anime_b = df.sample(1).iloc[0]
    st.session_state.game_over = False
    st.session_state.show_result = False
    st.session_state.image_revealed = False


def next_round():
    """Passe au round suivant."""
    df = st.session_state.df_animes
    st.session_state.anime_a = st.session_state.anime_b
    st.session_state.anime_b = df.sample(1).iloc[0]
    st.session_state.show_result = False
    st.session_state.image_revealed = False


def check_answer(guess_is_higher):
    """Vérifie la réponse du joueur."""
    a_score = st.session_state.anime_a['score']
    b_score = st.session_state.anime_b['score']
    
    correct = (b_score >= a_score) if guess_is_higher else (b_score < a_score)
    
    st.session_state.show_result = True
    st.session_state.last_correct = correct
    st.session_state.revealed_score = b_score
    
    if correct:
        st.session_state.score += 1
        st.session_state.streak += 1
        if st.session_state.streak > st.session_state.best_streak:
            st.session_state.best_streak = st.session_state.streak
        logger.info(f"✅ Bonne réponse ! Score: {st.session_state.score}, Streak: {st.session_state.streak}")
    else:
        logger.info(f"❌ Game Over ! Score final: {st.session_state.score}, Meilleur streak: {st.session_state.best_streak}")
        st.session_state.game_over = True
        st.session_state.streak = 0


# ============================================================================
# COMPOSANTS UI
# ============================================================================

def load_css():
    """Charge le fichier CSS externe."""
    # Global styles
    global_css = Path(__file__).parent.parent / "styles" / "global_styles.css"
    with open(global_css) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    
    # Higher or Lower styles
    css_file = Path(__file__).parent.parent / "styles" / "higher_lower_styles.css"
    with open(css_file) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def render_header():
    """Affiche le titre et sous-titre du jeu."""
    st.markdown("""
        <h1 class="main-title">
            HIGHER or LOWER
        </h1>
    """, unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Devinez si le score de l\'anime suivant est plus haut ou plus bas !</p>', unsafe_allow_html=True)


def render_metrics():
    """Affiche les métriques (score, série, record)."""
    col_score, col_streak, col_best = st.columns(3)
    
    with col_score:
        st.markdown(f"""
            <div class="custom-metric">
                <div class="metric-label">
                    <svg class="icon-svg" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <circle cx="12" cy="12" r="10" stroke="white" stroke-width="2"/>
                        <path d="M12 6V12L16 14" stroke="white" stroke-width="2" stroke-linecap="round"/>
                    </svg>
                    SCORE
                </div>
                <div class="metric-value">{st.session_state.score}</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col_streak:
        st.markdown(f"""
            <div class="custom-metric">
                <div class="metric-label">
                    <svg class="icon-svg" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M12 2C12 2 6 8 6 13C6 16.866 8.68629 20 12 20C15.3137 20 18 16.866 18 13C18 8 12 2 12 2Z" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                        <path d="M12 20C13.6569 20 15 18.2091 15 16C15 13.5 12 11 12 11C12 11 9 13.5 9 16C9 18.2091 10.3431 20 12 20Z" fill="white"/>
                    </svg>
                    SÉRIE
                </div>
                <div class="metric-value">{st.session_state.streak}</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col_best:
        st.markdown(f"""
            <div class="custom-metric">
                <div class="metric-label">
                    <svg class="icon-svg" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" fill="white" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    RECORD
                </div>
                <div class="metric-value">{st.session_state.best_streak}</div>
            </div>
        """, unsafe_allow_html=True)


def render_anime_card_a():
    """Affiche la card de l'anime A (score révélé)."""
    score_a = st.session_state.anime_a['score'] / 10
    cover_a = st.session_state.anime_a.get('cover_image', '')
    
    return f"""
        <div class="anime-card">
            <div style="position: relative; overflow: hidden;">
                <img src="{cover_a}" class="anime-cover" alt="{st.session_state.anime_a['title']}" />
                <div class="cover-overlay"></div>
            </div>
            <div class="anime-card-content">
                <div class="label-tag">
                    <svg class="icon-svg" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <rect x="2" y="3" width="20" height="14" rx="2" stroke="white" stroke-width="2"/>
                        <path d="M2 7H22" stroke="white" stroke-width="2"/>
                        <circle cx="6" cy="5" r="0.5" fill="white"/>
                        <circle cx="8" cy="5" r="0.5" fill="white"/>
                        <circle cx="10" cy="5" r="0.5" fill="white"/>
                        <path d="M9 11L12 14L16 10" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    ANIME A
                </div>
                <div class="anime-title">{st.session_state.anime_a['title']}</div>
                <div class="score-display">{score_a:.1f}/10</div>
                <div style="margin-top: 1rem; padding: 0 1rem;">
                    <div style="background: rgba(255,255,255,0.3); border-radius: 10px; height: 10px; overflow: hidden;">
                        <div style="background: white; height: 100%; width: {score_a * 10}%; transition: width 1s cubic-bezier(0.68, -0.55, 0.265, 1.55);"></div>
                    </div>
                </div>
            </div>
        </div>
    """


def render_anime_card_b_hidden():
    """Affiche la card de l'anime B (score caché)."""
    cover_b = st.session_state.anime_b.get('cover_image', '')
    blur_class = "" if st.session_state.get('image_revealed', False) else "anime-cover-blur"
    
    return f"""
        <div class="anime-card-hidden">
            <div style="position: relative; overflow: hidden;">
                <img src="{cover_b}" class="anime-cover {blur_class}" alt="???" />
                <div class="cover-overlay"></div>
            </div>
            <div class="anime-card-content">
                <div class="label-tag">
                    <svg class="icon-svg" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <rect x="2" y="3" width="20" height="14" rx="2" stroke="white" stroke-width="2"/>
                        <path d="M2 7H22" stroke="white" stroke-width="2"/>
                        <circle cx="6" cy="5" r="0.5" fill="white"/>
                        <circle cx="8" cy="5" r="0.5" fill="white"/>
                        <circle cx="10" cy="5" r="0.5" fill="white"/>
                        <path d="M12 10V12M12 14H12.01" stroke="white" stroke-width="2" stroke-linecap="round"/>
                    </svg>
                    ANIME B
                </div>
                <div class="anime-title">{st.session_state.anime_b['title']}</div>
                <div class="score-hidden">???</div>
                <div style="font-size: 1.2rem; margin-top: 1rem; font-weight: 600;">
                    Plus haut ou plus bas ?
                </div>
            </div>
        </div>
    """


def render_anime_card_b_revealed():
    """Affiche la card de l'anime B (score révélé avec résultat)."""
    score_b = st.session_state.revealed_score / 10
    cover_b = st.session_state.anime_b.get('cover_image', '')
    
    is_correct = st.session_state.last_correct
    bg_color = "linear-gradient(135deg, #11998e 0%, #38ef7d 100%)" if is_correct else "linear-gradient(135deg, #f5576c 0%, #f093fb 100%)"
    animation_class = "result-card-correct" if is_correct else "result-card-wrong"
    
    icon_svg = '''<svg class="icon-svg-large" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="10" stroke="white" stroke-width="2" fill="none"/>
        <path d="M8 12L11 15L16 9" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>''' if is_correct else '''<svg class="icon-svg-large" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="10" stroke="white" stroke-width="2" fill="none"/>
        <path d="M8 8L16 16M16 8L8 16" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
    </svg>'''
    
    text = "CORRECT !" if is_correct else "FAUX !"
    
    return f"""
        <div class="{animation_class}" style="background: {bg_color}; 
                    border-radius: 20px; padding: 0; color: white;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                    text-align: center; min-height: 450px;
                    overflow: hidden;">
            <div style="position: relative; overflow: hidden;">
                <img src="{cover_b}" class="anime-cover" alt="{st.session_state.anime_b['title']}" />
                <div class="cover-overlay"></div>
            </div>
            <div class="anime-card-content">
                <div class="label-tag">
                    <svg class="icon-svg" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <rect x="2" y="3" width="20" height="14" rx="2" stroke="white" stroke-width="2"/>
                        <path d="M2 7H22" stroke="white" stroke-width="2"/>
                        <circle cx="6" cy="5" r="0.5" fill="white"/>
                        <circle cx="8" cy="5" r="0.5" fill="white"/>
                        <circle cx="10" cy="5" r="0.5" fill="white"/>
                    </svg>
                    ANIME B
                </div>
                <div class="anime-title">{st.session_state.anime_b['title']}</div>
                <div style="font-size: 2rem; font-weight: 700; margin: 1rem 0; animation: bounceIn 0.5s ease-out;">
                    {icon_svg} {text}
                </div>
                <div class="score-display">{score_b:.1f}/10</div>
                <div style="margin-top: 1rem; padding: 0 1rem;">
                    <div style="background: rgba(255,255,255,0.3); border-radius: 10px; height: 10px; overflow: hidden;">
                        <div style="background: white; height: 100%; width: {score_b * 10}%; transition: width 1s cubic-bezier(0.68, -0.55, 0.265, 1.55);"></div>
                    </div>
                </div>
            </div>
        </div>
        <style>
        @keyframes bounceIn {{
            from {{ transform: scale(0); opacity: 0; }}
            50% {{ transform: scale(1.2); }}
            to {{ transform: scale(1); opacity: 1; }}
        }}
        </style>
    """


def render_game_buttons():
    """Affiche les boutons de jeu (Révéler + Plus haut/Plus bas)."""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Bouton révéler (si pas encore révélé)
        if not st.session_state.get('image_revealed', False):
            if st.button("Révéler l'image", use_container_width=True, key="btn_reveal"):
                st.session_state.image_revealed = True
                st.rerun()
            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        
        # Boutons Higher / Lower
        button_class = "game-buttons-appear" if st.session_state.get('image_revealed', False) else ""
        st.markdown(f'<div class="button-container {button_class}">', unsafe_allow_html=True)
        
        subcol1, subcol2 = st.columns(2)
        with subcol1:
            st.markdown("""
                <div style="text-align: center;">
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="margin-bottom: 8px;">
                        <path d="M12 4L12 20M12 4L8 8M12 4L16 8" stroke="#667eea" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </div>
            """, unsafe_allow_html=True)
            if st.button("PLUS HAUT", type="primary", use_container_width=True, key="btn_higher"):
                check_answer(True)
                st.rerun()
        
        with subcol2:
            st.markdown("""
                <div style="text-align: center;">
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="margin-bottom: 8px;">
                        <path d="M12 20L12 4M12 20L8 16M12 20L16 16" stroke="#f5576c" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </div>
            """, unsafe_allow_html=True)
            if st.button("PLUS BAS", type="secondary", use_container_width=True, key="btn_lower"):
                check_answer(False)
                st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)


def render_game_over():
    """Affiche l'écran Game Over."""
    st.markdown("""
        <h2 class="game-over-title">
            <svg class="icon-svg-large" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="10" stroke="#f5576c" stroke-width="2"/>
                <path d="M8 8L16 16M16 8L8 16" stroke="#f5576c" stroke-width="2" stroke-linecap="round"/>
            </svg>
            GAME OVER
        </h2>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f"""
            <div style="background: linear-gradient(135deg, #f5576c 0%, #f093fb 100%); 
                        border-radius: 20px; padding: 2rem; text-align: center; color: white;
                        box-shadow: 0 10px 30px rgba(245, 87, 108, 0.3);">
                <div style="font-size: 1.2rem; margin-bottom: 1rem;">Score final</div>
                <div style="font-size: 4rem; font-weight: 900;">{st.session_state.score}</div>
                <div style="font-size: 1rem; margin-top: 1rem; opacity: 0.9;">
                    Le score de <strong>{st.session_state.anime_b['title']}</strong> était 
                    <strong>{st.session_state.revealed_score / 10:.1f}/10</strong>
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("RECOMMENCER", type="primary", use_container_width=True):
            init_game()
            st.rerun()


# ============================================================================
# FONCTION PRINCIPALE
# ============================================================================

def show():
    """Affiche la page du jeu Higher or Lower."""
    
    # Charger le CSS
    load_css()
    
    # Header
    render_header()
    
    # Chargement des données
    if 'df_animes' not in st.session_state:
        with st.spinner("Chargement des animes..."):
            st.session_state.df_animes = load_game_data(top_k=500)
    
    # Initialisation du jeu
    if 'score' not in st.session_state:
        init_game()
    
    # Métriques
    render_metrics()
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Game Over ?
    if st.session_state.game_over:
        render_game_over()
        return
    
    # Affichage des animes
    col1, col_vs, col2 = st.columns([5, 1, 5])
    
    with col1:
        st.markdown(render_anime_card_a(), unsafe_allow_html=True)
    
    with col_vs:
        st.markdown('<div class="vs-container"><div class="vs-badge">VS</div></div>', unsafe_allow_html=True)
    
    with col2:
        if st.session_state.show_result:
            st.markdown(render_anime_card_b_revealed(), unsafe_allow_html=True)
        else:
            st.markdown(render_anime_card_b_hidden(), unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Boutons
    if st.session_state.show_result:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown('<div class="button-container">', unsafe_allow_html=True)
            if st.button("ANIME SUIVANT", type="primary", use_container_width=True, key="btn_next"):
                next_round()
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        render_game_buttons()
    
    # Bouton reset
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([2, 1, 2])
    with col2:
        if st.button("Nouveau jeu", use_container_width=True, key="btn_reset"):
            init_game()
            st.rerun()


# ============================================================================
# SIDEBAR
# ============================================================================

def render_sidebar():
    """Affiche la sidebar personnalisée."""
    with st.sidebar:
        # Logo/Header
        st.markdown("""
        <div class="sidebar-logo">
            <svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="2" y="7" width="20" height="15" rx="2" ry="2"></rect>
                <polyline points="17 2 12 7 7 2"></polyline>
                <circle cx="8" cy="14" r="1"></circle>
                <circle cx="16" cy="14" r="1"></circle>
            </svg>
            <div class="sidebar-logo-title">Higher or Lower</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Navigation
        st.markdown('<div class="sidebar-section-title">Navigation</div>', unsafe_allow_html=True)
        st.page_link("app.py", label="Accueil")
        st.page_link("pages/2_anime_recommender.py", label="Recommender")
        st.page_link("pages/1_higher_lower.py", label="Higher or Lower")
        st.page_link("pages/3_recherche_sementique.py", label="Recherche Sémantique")

        
        st.markdown("---")
        
        # Stats actuelles
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-section-title">Session actuelle</div>', unsafe_allow_html=True)
        score = st.session_state.get('score', 0)
        streak = st.session_state.get('streak', 0)
        best = st.session_state.get('best_streak', 0)
        st.markdown(f"**Score** : {score}")
        st.markdown(f"**Streak** : {streak}")
        st.markdown(f"**Meilleur** : {best}")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Règles du jeu
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-section-title">Comment jouer</div>', unsafe_allow_html=True)
        st.markdown("1. Compare deux animes")
        st.markdown("2. Devine lequel a le meilleur score")
        st.markdown("3. Enchaîne les bonnes réponses")
        st.markdown("4. Bats ton record")
        st.markdown('</div>', unsafe_allow_html=True)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    render_sidebar()
    show()
