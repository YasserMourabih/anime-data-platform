import streamlit as st
from pathlib import Path
import pandas as pd
import sqlalchemy
import os
import re
from sqlalchemy import text
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

# --- CONFIGURATION ---

# --- CSS EXTERNE ---
def load_css():
    global_css = Path(__file__).parent.parent / "styles" / "global_styles.css"
    with open(global_css) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    semantic_css = Path(__file__).parent.parent / "styles" / "semantic_search_styles.css"
    with open(semantic_css) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()
load_dotenv() # Charge les secrets (DB_USER, etc.) depuis le cloud Streamlit
MODEL_NAME = 'all-MiniLM-L6-v2' # Doit être le MÊME modèle que Dagster


def normalize_franchise_title(title):
    """Nettoie le titre pour identifier la franchise principale."""
    if not title: return ""
    # On passe en minuscule
    t = title.lower()
    # On enlève les "Season 2", "2nd Season", "Part 2", ": Movie", etc.
    # C'est une regex simplifiée mais efficace
    t = re.sub(r'\s*(:|season|part|\d+nd|\d+th|\d+rd).*', '', t)
    return t.strip()

# --- CACHING (Très important) ---

@st.cache_resource
def load_ia_model():
    """
    Charge le modèle d'IA en mémoire.
    @st.cache_resource le garde en cache pour toute la session,
    évitant de le recharger (ce qui est très lent) à chaque clic.
    """
    try:
        model = SentenceTransformer(MODEL_NAME)
        return model
    except Exception as e:
        st.error(f"Erreur critique lors du chargement du modèle d'IA : {e}")
        return None

@st.cache_resource(ttl=3600) # Cache la connexion 1h
def get_db_engine():
    """Crée et retourne un engine SQLAlchemy pour Neon."""
    try:
        db_url = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}?sslmode=require"
        return sqlalchemy.create_engine(db_url)
    except Exception as e:
        st.error(f"Erreur de connexion à la base de données : {e}")
        return None
    
@st.cache_data
def get_all_genres():
    """Récupère la liste unique des genres pour le filtre."""
    try:
        # On utilise la vue view_anime_genres qui a déjà "éclaté" les genres
        df = pd.read_sql("SELECT DISTINCT genre FROM view_anime_genres ORDER BY genre", engine)
        return df['genre'].tolist()
    except:
        return []

# --- CHARGEMENT DES RESSOURCES ---
model = load_ia_model()
engine = get_db_engine()
all_genres = get_all_genres()

# --- INTERFACE UTILISATEUR (UI) ---


st.markdown("""
    <h1 class="main-title">Recherche Sémantique</h1>
""", unsafe_allow_html=True)
st.markdown('<p class="subtitle">Trouve des animes par ambiance, synopsis ou description narrative. L\'IA comprend le <b>sens</b> de ta recherche !</p>', unsafe_allow_html=True)
st.markdown("---")

# --- SIDEBAR PERSONNALISÉE ---
with st.sidebar:
    st.markdown("""
    <div class="sidebar-logo">
        <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <path d="M8 12L12 16L16 12" stroke="white" stroke-width="2" stroke-linecap="round"/>
        </svg>
        <div class="sidebar-logo-title">Recherche Sémantique</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="sidebar-section-title">Navigation</div>', unsafe_allow_html=True)
    st.page_link("app.py", label="Accueil")
    st.page_link("pages/2_anime_recommender.py", label="Recommender")
    st.page_link("pages/1_higher_lower.py", label="Higher or Lower")
    st.page_link("pages/3_recherche_sementique.py", label="Recherche Sémantique")
    st.markdown("---")
    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-section-title">À propos</div>', unsafe_allow_html=True)
    st.markdown("""
    Ce moteur utilise l'IA pour comprendre le <b>sens</b> de ta recherche et te proposer les animes les plus pertinents.<br>
    <ul>
        <li>Recherche sémantique (embedding)</li>
        <li>Filtrage par genres et score</li>
        <li>Dédoublonnage des franchises</li>
    </ul>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("---")

query_text = st.text_input("Recherchez une ambiance ou une histoire :", 
                           placeholder="Ex: un lycéen obtient un pouvoir pour tuer des gens")

if query_text and model and engine:
    with st.spinner("Calcul en cours... L'IA transforme votre pensée en vecteur..."):
        # 1. Transformer la recherche de l'utilisateur en vecteur
        query_vector = model.encode(query_text)

    with st.sidebar:
        st.header("Filtres de Recherche")
        
        # Filtre par Genre
        selected_genres = st.multiselect(
            "Filtrer par Genres (ET)",
            options=all_genres,
            help="L'anime doit contenir TOUS les genres sélectionnés"
        )
    
    # Filtre par Score Min
    min_score = st.slider("Score minimum", 0, 100, 50)
    
    # Filtre par Année (Optionnel mais cool)
    # min_year = st.number_input("Sorti après l'année", 1970, 2025, 2000)

    with st.spinner("Recherche Hybride (Sémantique + Filtres)..."):
        # 1. Construction de la clause WHERE dynamique
        where_clauses = ["t2.score >= :min_score"]
        params = {
            "query_vec": str(query_vector.tolist()),
            "min_score": min_score
        }
        
        # Si des genres sont sélectionnés, on ajoute le filtre JSONB
        if selected_genres:
            # On formate la liste Python en chaîne JSON pour Postgres : '["Action", "Sci-Fi"]'
            import json
            genres_json = json.dumps(selected_genres)
            
            # CORRECTION ICI : Utilisation de CAST au lieu de ::
            where_clauses.append("CAST(t2.genres AS jsonb) @> CAST(:genres_filter AS jsonb)")
            
            params["genres_filter"] = genres_json

        # On joint toutes les clauses avec AND
        where_sql = " AND ".join(where_clauses)

        # 2. La Requête Finale
        sql_query = text(f"""
            SELECT
                t1.title,
                t2.description,
                t2.score,
                t2.start_year,
                t2.genres, -- On récupère aussi les genres pour l'affichage
                (t1.embedding <-> :query_vec) AS distance
            FROM
                anime_embeddings AS t1
            JOIN
                view_anime_basic AS t2 ON t1.anime_id = t2.anime_id
            WHERE
                {where_sql}
            ORDER BY
                distance ASC
            LIMIT 30
        """)
        
        with engine.connect() as conn:
            result = conn.execute(sql_query, params)
            candidates = result.fetchall()

        # --- ÉTAPE 2 : FILTER (Dédoublonnage et Sélection) ---
        final_results = []
        seen_franchises = set()
        
        for row in candidates:
            # On récupère le titre nettoyé (ex: "Attack on Titan")
            franchise_name = normalize_franchise_title(row.title)
            
            # Si on a déjà vu cette franchise, on saute (c'est une saison 2 ou 3...)
            if franchise_name in seen_franchises:
                continue
            
            # Sinon, on l'ajoute aux résultats
            final_results.append(row)
            seen_franchises.add(franchise_name)
            
            # Dès qu'on a 10 animes UNIQUES, on s'arrête
            if len(final_results) >= 10:
                break

    # 3. Affichage (inchangé, mais on utilise final_results)
    st.subheader("Résultats les plus pertinents :")
    
    if not final_results:
        st.info("Aucun résultat trouvé.")
    else:
        for index, row in enumerate(final_results):
            similarity = max(0, 1 - (row.distance / 1.4))
            score_emoji = "⭐" if row.score and row.score >= 80 else "😐"
            st.markdown(f"""
                <div class="semantic-card">
                    <div class="result-meta">
                        <span class="score-badge">{score_emoji} {row.score}/100</span>
                        Année : {row.start_year}
                    </div>
                    <div class="anime-title">{index+1}. {row.title}</div>
                    <div class="progress-bar">
                        <div class="progress-bar-inner" style="width:{int(similarity*100)}%"></div>
                    </div>
                    <div style="font-size:0.95rem;color:#666;margin-bottom:0.5rem;">Pertinence : {int(similarity*100)}%</div>
                    <div class="result-description">{row.description[:350] + '...' if row.description else ''}</div>
                </div>
            """, unsafe_allow_html=True)
elif not model:
    st.error("Le modèle d'IA n'a pas pu être chargé. L'application ne peut pas fonctionner.")
elif not engine:
    st.error("La connexion à la base de données a échoué.")