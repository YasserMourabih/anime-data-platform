"""
Assets Dagster du pipeline anime-data-platform.

Ce module définit les trois assets du pipeline :
- raw_anilist_data       : Extraction depuis l'API AniList → PostgreSQL
- anime_recommendations  : Calcul TF-IDF → fichier Parquet local
- deploy_recommendations : Déploiement du Parquet (local ou GitHub Releases)

Les assets sont des wrappers légers autour des fonctions métier de src/.
La logique métier reste indépendante de Dagster pour faciliter les tests.
"""

import time

from dagster import AssetExecutionContext, MaterializeResult, MetadataValue, asset

from orchestration.resources import DatabaseResource
from src.compute_recommendations import compute_and_save_recommendations
from src.config import MAX_PAGES_TO_FETCH, PARQUET_LOCAL_PATH
from src.extract import extract_anilist_data


@asset(
    group_name="ingestion",
    description="Extrait les données AniList et les charge dans PostgreSQL (raw_anilist_json).",
)
def raw_anilist_data(
    context: AssetExecutionContext,
    database: DatabaseResource,
) -> MaterializeResult:
    """
    Extrait les données brutes de l'API AniList et les persiste dans PostgreSQL.

    Délègue l'orchestration à extract_anilist_data() en lui injectant
    la connexion BDD et le logger Dagster.
    """
    context.log.info("Démarrage de l'extraction AniList...")

    metrics = extract_anilist_data(
        db_url=database.url,
        max_pages=MAX_PAGES_TO_FETCH,
        logger=context.log,
    )

    context.log.info(f"Extraction terminée : {metrics['num_records']} animes")

    return MaterializeResult(
        metadata={
            "num_records": metrics["num_records"],
            "pages_processed": metrics["pages_processed"],
            "duration_seconds": metrics["duration_seconds"],
            "avg_records_per_page": metrics["avg_records_per_page"],
            "preview": MetadataValue.md(
                f"**{metrics['num_records']:,} animes** extraits "
                f"en {metrics['duration_seconds']:.0f}s "
                f"({metrics['pages_processed']} pages)"
            ),
        }
    )


@asset(
    group_name="ml",
    description="Calcule les recommandations TF-IDF et génère le fichier Parquet.",
    deps=[raw_anilist_data],
)
def anime_recommendations(
    context: AssetExecutionContext,
    database: DatabaseResource,
) -> MaterializeResult:
    """
    Calcule les recommandations d'animes par similarité TF-IDF.

    Délègue le calcul à compute_and_save_recommendations() en lui injectant
    la connexion BDD et le logger Dagster.
    """
    context.log.info("Démarrage du calcul des recommandations...")
    start_time = time.time()

    metrics = compute_and_save_recommendations(
        db_url=database.url,
        output_file=str(PARQUET_LOCAL_PATH),
        logger=context.log,
    )

    duration = time.time() - start_time
    context.log.info(f"Recommandations générées en {duration:.2f}s")

    return MaterializeResult(
        metadata={
            "total_animes": metrics["total_animes"],
            "total_recommendations": metrics["total_recommendations"],
            "avg_recommendations_per_anime": metrics["avg_recommendations_per_anime"],
            "combined_matrix_shape": metrics["combined_matrix_shape"],
            "file_size_mb": metrics["file_size_mb"],
            "duration_seconds": round(duration, 2),
            "preview": MetadataValue.md(
                f"**{metrics['total_animes']:,} animes** · "
                f"**{metrics['total_recommendations']:,} recommandations** · "
                f"{metrics['file_size_mb']:.2f} MB"
            ),
        }
    )


@asset(
    group_name="deploy",
    description="Déploie le fichier Parquet (local : no-op / cloud : GitHub Releases).",
    deps=[anime_recommendations],
    required_resource_keys={"parquet_storage"},
)
def deploy_recommendations(context: AssetExecutionContext) -> MaterializeResult:
    """
    Déploie le fichier Parquet selon le mode de déploiement configuré.

    En mode local, confirme simplement la disponibilité du fichier.
    En mode cloud, uploade vers GitHub Releases pour l'app Streamlit.

    La resource 'parquet_storage' est injectée par Dagster selon DEPLOYMENT_MODE
    (LocalParquetStorage ou GitHubReleasesStorage, configuré dans definitions.py).
    """
    context.log.info("Démarrage du déploiement...")
    parquet_storage = context.resources.parquet_storage

    result = parquet_storage.deploy(str(PARQUET_LOCAL_PATH), context.log)

    return MaterializeResult(
        metadata={
            **result,
            "preview": MetadataValue.md(
                f"**Status** : `{result['status']}`\n\n"
                + (
                    f"**URL** : {result.get('download_url', result.get('path', ''))}"
                )
            ),
        }
    )
