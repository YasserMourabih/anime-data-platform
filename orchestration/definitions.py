"""
Point d'entrée Dagster du projet anime-data-platform.

Ce module configure :
- Les assets du pipeline (extraction, ML, déploiement)
- Les ressources injectées selon DEPLOYMENT_MODE ("local" ou "cloud")
- Le job de mise à jour complète de la plateforme
- Le schedule hebdomadaire (dimanche à 03:00 UTC)

Pour changer de mode, modifier DEPLOYMENT_MODE dans votre fichier .env :
    DEPLOYMENT_MODE=local   → PostgreSQL local, parquet sur disque
    DEPLOYMENT_MODE=cloud   → PostgreSQL Neon, parquet sur GitHub Releases
"""

import os
import sys

# Ajoute la racine du projet au PYTHONPATH pour permettre les imports depuis src/
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from dagster import (
    Definitions,
    EnvVar,
    ScheduleDefinition,
    define_asset_job,
    load_assets_from_modules,
)

from orchestration import assets
from orchestration.resources import DatabaseResource, GitHubReleasesStorage, LocalParquetStorage
from src.config import DATABASE_URL, DEPLOYMENT_MODE

# ─── Assets ───────────────────────────────────────────────────────────────────
all_assets = load_assets_from_modules([assets])

# ─── Job ──────────────────────────────────────────────────────────────────────
update_all_job = define_asset_job(
    name="update_anime_platform",
    selection="*",
    description="Lance l'extraction AniList, le calcul ML et le déploiement en une seule exécution.",
)

# ─── Schedule ─────────────────────────────────────────────────────────────────
weekly_update_schedule = ScheduleDefinition(
    job=update_all_job,
    cron_schedule="0 3 * * 0",  # Dimanche à 03:00 UTC
    description="Mise à jour hebdomadaire de la plateforme.",
)

# ─── Resources ────────────────────────────────────────────────────────────────
database_resource = DatabaseResource(url=DATABASE_URL)

if DEPLOYMENT_MODE == "cloud":
    parquet_storage_resource = GitHubReleasesStorage(
        token=EnvVar("GITHUB_TOKEN"),
        repo=EnvVar("GITHUB_REPO"),
        release_tag=EnvVar("GITHUB_RELEASE_TAG"),
    )
else:
    # Mode local (défaut) : le parquet reste dans data/
    parquet_storage_resource = LocalParquetStorage()

# ─── Definitions ──────────────────────────────────────────────────────────────
defs = Definitions(
    assets=all_assets,
    jobs=[update_all_job],
    schedules=[weekly_update_schedule],
    resources={
        "database": database_resource,
        "parquet_storage": parquet_storage_resource,
    },
)
