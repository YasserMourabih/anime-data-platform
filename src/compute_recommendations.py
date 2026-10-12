"""
Module de calcul des recommandations d'animes par similarité TF-IDF.

Pipeline de traitement :
1. Chargement des animes, genres et tags depuis PostgreSQL
2. Filtrage par score et popularité
3. Construction de deux matrices TF-IDF séparées :
   - Métadonnées (genres + tags), pondération WEIGHT_META
   - Synopsis, pondération WEIGHT_DESC
4. Calcul de similarité cosinus sur la matrice combinée
5. Génération des recommandations avec déduplications par franchise
6. Sauvegarde au format Parquet

Peut être exécuté depuis :
- Un asset Dagster (logger Dagster injecté)
- Un script CLI (logger standard Python)
"""

import logging
import os
import re
from pathlib import Path

import pandas as pd
import sqlalchemy
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

from src.config import (
    DATABASE_URL,
    MAX_ANIME_PER_RUN,
    MIN_ANIME_SCORE,
    PARQUET_LOCAL_PATH,
    TFIDF_DESC_MAX_DF,
    TFIDF_DESC_MAX_FEATURES,
    TFIDF_DESC_MIN_DF,
    TFIDF_DESC_NGRAM_RANGE,
    TFIDF_META_MIN_DF,
    TOP_K_RECOMMENDATIONS,
    WEIGHT_DESC,
    WEIGHT_META,
    logger,
)


def _get_logger(external_logger=None) -> logging.Logger:
    """Retourne le logger externe (Dagster) s'il est fourni, sinon le logger du module."""
    return external_logger if external_logger else logger


def clean_html(raw_html: str) -> str:
    """
    Supprime les balises HTML d'une chaîne de caractères.

    Args:
        raw_html: Texte potentiellement balisé HTML.

    Les balises sont remplacées par une espace (et non supprimées) pour éviter
    de coller deux mots séparés par un <br>, ce qui créerait un faux token TF-IDF.

    Returns:
        str: Texte nettoyé, sans balises ni espaces superflus.
    """
    if not raw_html:
        return ""
    text = re.sub(r"<.*?>", " ", raw_html)
    return re.sub(r"\s+", " ", text).strip()


def extract_franchise_name(title: str) -> str:
    """
    Normalise un titre d'anime en nom de franchise racine.

    Supprime les suffixes courants (saisons, films, OVA, etc.) pour permettre
    le regroupement des œuvres d'une même franchise lors de la déduplication.

    Exemples:
        "Naruto: Shippuden"          → "naruto"
        "Attack on Titan Season 2"   → "attack on titan"
        "One Piece Film: Red"        → "one piece"

    Args:
        title: Titre de l'anime tel que retourné par l'API AniList.

    Returns:
        str: Nom de franchise normalisé en minuscules.
    """
    if not title:
        return ""

    franchise = title.lower()
    patterns = [
        r"\s*:\s*.*",
        r"\s+season\s+\d+.*",
        r"\s+\d+(st|nd|rd|th)\s+season.*",
        r"\s+part\s+\d+.*",
        r"\s+movie.*",
        r"\s+film.*",
        r"\s+ova.*",
        r"\s+ona.*",
        r"\s+special.*",
        r"\s+recap.*",
        r"\s+\(.*\)$",
        r"\s+\d+$",
        r"\s+ii$",
        r"\s+iii$",
        r"\s+iv$",
        r"\s+v$",
    ]

    for pattern in patterns:
        franchise = re.sub(pattern, "", franchise, flags=re.IGNORECASE)

    franchise = re.sub(r"\s+", " ", franchise).strip()

    if len(franchise) < 3 and title:
        words = title.lower().split()
        franchise = " ".join(words[: min(3, len(words))])

    return franchise


def compute_and_save_recommendations(
    db_url: str = None,
    output_file: str = None,
    top_k: int = None,
    logger=None,
) -> dict:
    """
    Calcule les recommandations d'animes par similarité TF-IDF et sauvegarde en Parquet.

    Args:
        db_url: URL de connexion PostgreSQL. Utilise DATABASE_URL de config si None.
        output_file: Chemin du fichier Parquet de sortie. Utilise PARQUET_LOCAL_PATH si None.
        top_k: Nombre de recommandations par anime. Utilise TOP_K_RECOMMENDATIONS si None.
        logger: Logger optionnel (Dagster ou logging standard).

    Returns:
        dict: Métriques d'exécution (nombre d'animes, recommandations, taille fichier, etc.).

    Raises:
        sqlalchemy.exc.SQLAlchemyError: En cas d'erreur de connexion ou de requête BDD.
    """
    log = _get_logger(logger)
    url = db_url or DATABASE_URL
    dest = Path(output_file) if output_file else PARQUET_LOCAL_PATH
    k = top_k if top_k is not None else TOP_K_RECOMMENDATIONS

    # 1. Connexion et chargement des données
    log.info("Connexion à la base de données...")
    engine = sqlalchemy.create_engine(url)

    log.info("Chargement des données depuis PostgreSQL...")
    df_anime = pd.read_sql(
        f"""
        SELECT anime_id, title, description, score
        FROM view_anime_basic
        WHERE score > {MIN_ANIME_SCORE} AND popularity IS NOT NULL
        ORDER BY popularity DESC
        LIMIT {MAX_ANIME_PER_RUN}
        """,
        engine,
    )
    df_genres = pd.read_sql("SELECT anime_id, genre FROM view_anime_genres", engine)
    df_tags = pd.read_sql("SELECT anime_id, tag FROM view_anime_tags", engine)

    log.info(f"{len(df_anime)} animes, {len(df_genres)} genres, {len(df_tags)} tags chargés")

    # 2. Filtrage par score et synchronisation genres/tags
    anime_ids = set(df_anime["anime_id"].unique())
    df_genres = df_genres[df_genres["anime_id"].isin(anime_ids)]
    df_tags = df_tags[df_tags["anime_id"].isin(anime_ids)]

    # 3. Nettoyage des synopsis
    log.info("Nettoyage des synopsis...")
    df_anime["description"] = df_anime["description"].apply(clean_html).fillna("")

    # 4. Construction de la soupe de métadonnées (genres + tags)
    log.info("Préparation des features (métadonnées + synopsis)...")
    features_meta = pd.concat(
        [
            df_genres.rename(columns={"genre": "feature"})[["anime_id", "feature"]],
            df_tags.rename(columns={"tag": "feature"})[["anime_id", "feature"]],
        ],
        ignore_index=True,
    )
    soup_meta = (
        features_meta.groupby("anime_id")["feature"]
        .apply(lambda x: " ".join(x.astype(str)))
        .reset_index()
        .rename(columns={"feature": "soup_meta"})
    )

    df_final = pd.merge(df_anime, soup_meta, on="anime_id", how="left")
    df_final["soup_meta"] = df_final["soup_meta"].fillna("")

    # 5. Vectorisation TF-IDF séparée
    log.info(
        f"Vectorisation TF-IDF (métadonnées {WEIGHT_META*100:.0f}% / synopsis {WEIGHT_DESC*100:.0f}%)..."
    )
    tfidf_meta = TfidfVectorizer(stop_words="english", min_df=TFIDF_META_MIN_DF)
    matrix_meta = tfidf_meta.fit_transform(df_final["soup_meta"])

    tfidf_desc = TfidfVectorizer(
        stop_words="english",
        ngram_range=TFIDF_DESC_NGRAM_RANGE,
        min_df=TFIDF_DESC_MIN_DF,
        max_df=TFIDF_DESC_MAX_DF,
        max_features=TFIDF_DESC_MAX_FEATURES,
    )
    matrix_desc = tfidf_desc.fit_transform(df_final["description"])

    log.info(f"Matrice métadonnées : {matrix_meta.shape}")
    log.info(f"Matrice synopsis    : {matrix_desc.shape}")

    # 6. Combinaison pondérée et calcul de similarité cosinus
    log.info("Combinaison pondérée et calcul de similarité cosinus...")
    combined_matrix = hstack([matrix_meta * WEIGHT_META, matrix_desc * WEIGHT_DESC])
    similarity_matrix = linear_kernel(combined_matrix, combined_matrix)

    # 7. Génération des recommandations avec déduplication par franchise
    log.info("Génération des recommandations...")
    reco_list = []

    for idx, row in df_final.iterrows():
        title = row["title"]
        sim_scores = sorted(enumerate(similarity_matrix[idx]), key=lambda x: x[1], reverse=True)
        # On prend k*10 candidats pour absorber les exclusions de franchise
        candidates = sim_scores[1 : k * 10]

        source_franchise = extract_franchise_name(title)
        seen_franchises = {source_franchise}
        count = 0

        for sim_idx, score in candidates:
            candidate_title = df_final.iloc[sim_idx]["title"]
            candidate_franchise = extract_franchise_name(candidate_title)

            if candidate_franchise in seen_franchises:
                continue
            if source_franchise in candidate_title.lower() or candidate_franchise in title.lower():
                continue

            reco_list.append((title, candidate_title, round(float(score), 3)))
            seen_franchises.add(candidate_franchise)
            count += 1

            if count >= k:
                break

        if (idx + 1) % 1000 == 0:
            log.info(f"{idx + 1}/{len(df_final)} animes traités...")

    # 8. Sauvegarde au format Parquet
    log.info("Sauvegarde au format Parquet...")
    df_recos = pd.DataFrame(reco_list, columns=["source_title", "reco_title", "score"])

    dest.parent.mkdir(parents=True, exist_ok=True)
    df_recos.to_parquet(dest, index=False)

    file_size_mb = os.path.getsize(dest) / (1024 * 1024)
    total_animes = df_recos["source_title"].nunique()
    total_recos = len(df_recos)

    log.info(f"Parquet sauvegardé : {dest} ({file_size_mb:.2f} MB, {total_animes} animes)")

    return {
        "total_animes": total_animes,
        "total_recommendations": total_recos,
        "avg_recommendations_per_anime": round(total_recos / max(total_animes, 1), 2),
        "combined_matrix_shape": f"{combined_matrix.shape[0]} x {combined_matrix.shape[1]}",
        "output_file": str(dest),
        "file_size_mb": round(file_size_mb, 2),
    }
