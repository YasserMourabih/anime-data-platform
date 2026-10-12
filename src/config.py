"""
Configuration centrale du projet anime-data-platform.

Ce module est le point unique de vérité pour toute la configuration.
Toutes les constantes, paramètres ML et variables d'environnement sont lues ici.

Usage:
    from src.config import DATABASE_URL, PARQUET_LOCAL_PATH, WEIGHT_META, ...
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ─── Deployment Mode ──────────────────────────────────────────────────────────
# "local"  → PostgreSQL local (docker-compose), parquet sauvegardé dans data/
# "cloud"  → PostgreSQL Neon, parquet uploadé vers GitHub Releases
DEPLOYMENT_MODE: str = os.getenv("DEPLOYMENT_MODE", "local")

# ─── AniList API ──────────────────────────────────────────────────────────────
ANILIST_API_URL: str = os.getenv("ANILIST_API_URL", "https://graphql.anilist.co")

# ─── Database ─────────────────────────────────────────────────────────────────
# Accepte soit DATABASE_URL directement (fourni par Neon, Docker, etc.)
# soit la construction depuis les variables individuelles DB_HOST, DB_USER, etc.
DATABASE_URL: str = os.getenv("DATABASE_URL") or (
    "postgresql://{user}:{password}@{host}:{port}/{name}?sslmode={ssl}".format(
        user=os.getenv("DB_USER", ""),
        password=os.getenv("DB_PASS", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        name=os.getenv("DB_NAME", "anime_db"),
        ssl=os.getenv("SSL_MODE", "prefer"),
    )
)

# ─── Extraction Pipeline ──────────────────────────────────────────────────────
MAX_PAGES_TO_FETCH: int = int(os.getenv("MAX_PAGES_TO_FETCH", "500"))  # 1 page = 50 animes

# ─── ML / Recommendations ─────────────────────────────────────────────────────
# Pondération TF-IDF : genres/tags vs synopsis
WEIGHT_META: float = 0.7
WEIGHT_DESC: float = 0.3

# Paramètres de sélection des animes
TOP_K_RECOMMENDATIONS: int = 10   # Nombre de recommandations par anime
MIN_ANIME_SCORE: int = 60         # Score minimum AniList (échelle 0-100)
MAX_ANIME_PER_RUN: int = 5000     # Nombre max d'animes chargés depuis la BDD

# Paramètres du vectorizer TF-IDF (métadonnées)
TFIDF_META_MIN_DF: int = 5

# Paramètres du vectorizer TF-IDF (synopsis)
TFIDF_DESC_MIN_DF: int = 10
TFIDF_DESC_MAX_DF: float = 0.5
TFIDF_DESC_MAX_FEATURES: int = 500
TFIDF_DESC_NGRAM_RANGE: tuple = (1, 2)

# ─── Storage ──────────────────────────────────────────────────────────────────
PARQUET_LOCAL_PATH: Path = Path(os.getenv("PARQUET_LOCAL_PATH", "data/recommendations.parquet"))

# Source du parquet pour l'application Streamlit :
# - local  → chemin vers le fichier local (produit par le pipeline Dagster)
# - cloud  → URL GitHub Releases (définie via PARQUET_URL dans .env)
PARQUET_SOURCE: str = (
    os.getenv("PARQUET_URL", "")
    if DEPLOYMENT_MODE == "cloud"
    else str(PARQUET_LOCAL_PATH)
)

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("anime_platform")
