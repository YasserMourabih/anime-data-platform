"""
Définition des assets Dagster pour le pipeline anime-data-platform.

Ce module contient les assets pour :
- raw_anilist_data : Extraction des données depuis l'API AniList
- anime_recommendations : Calcul des recommandations basées sur TF-IDF

Les assets sont des wrappers légers autour des fonctions métier,
permettant une séparation claire entre orchestration et logique métier.
"""

from dagster import asset, MaterializeResult, AssetExecutionContext
import time
from src.extract import extract_anilist_data
from src.config import MAX_PAGES_TO_FETCH
from src.compute_recommendations import compute_and_save_recommendations


@asset(
    group_name="ingestion",
    description="Extrait les données d'AniList et les charge dans Postgres (raw_anilist_json)"
)
def raw_anilist_data(context: AssetExecutionContext) -> MaterializeResult:
    """
    Asset représentant les données brutes AniList dans PostgreSQL.
    
    Cet asset est un simple wrapper autour de la fonction métier extract_anilist_data.
    La séparation permet de tester la logique métier indépendamment de Dagster.
    """
    context.log.info("🚀 Démarrage de l'extraction AniList via Dagster...")
    
    # Appeler la fonction métier avec le logger Dagster
    metadata = extract_anilist_data(
        max_pages=MAX_PAGES_TO_FETCH,
        delay_between_pages=2,
        logger=context.log
    )
    
    context.log.info(f"✅ Extraction terminée : {metadata['num_records']} animes")
    
    return MaterializeResult(metadata=metadata)


@asset(
    group_name="ml",
    description="Calcule et sauvegarde les recommandations d'anime basées sur TF-IDF (genres + tags)",
    deps=[raw_anilist_data]  # Dépend de l'extraction
)
def anime_recommendations(context: AssetExecutionContext) -> MaterializeResult:
    """
    Asset Dagster qui génère des recommandations d'animes.
    
    Cet asset est un simple wrapper autour de la fonction métier compute_and_save_recommendations.
    La séparation permet de tester la logique métier indépendamment de Dagster.
    """
    context.log.info("🧮 Démarrage du calcul des recommandations...")
    
    start_time = time.time()
    
    # Appeler la fonction métier avec le logger Dagster
    metadata = compute_and_save_recommendations(logger=context.log)
    
    # Ajouter le temps d'exécution
    duration = time.time() - start_time
    metadata["duration_seconds"] = round(duration, 2)
    
    context.log.info(f"✅ Recommandations générées en {duration:.2f}s")
    
    return MaterializeResult(metadata=metadata)