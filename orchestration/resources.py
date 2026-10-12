"""
Ressources Dagster pour le projet anime-data-platform.

Ce module définit les ressources injectables qui varient selon le mode de déploiement :
- DatabaseResource    : connexion PostgreSQL (identique local/cloud, seule l'URL change)
- LocalParquetStorage : stockage parquet sur disque local (mode "local")
- GitHubReleasesStorage : upload parquet vers GitHub Releases (mode "cloud")

Le mode actif est sélectionné dans definitions.py via la variable DEPLOYMENT_MODE.
"""

import os

import psycopg2
import requests
import sqlalchemy
from dagster import ConfigurableResource


class DatabaseResource(ConfigurableResource):
    """
    Ressource Dagster encapsulant la connexion à PostgreSQL.

    Fournit deux interfaces :
    - get_engine()     : moteur SQLAlchemy pour pandas.read_sql()
    - get_connection() : connexion psycopg2 pour les insertions en masse
    """

    url: str

    def get_engine(self) -> sqlalchemy.Engine:
        """Retourne un moteur SQLAlchemy pour les requêtes de lecture."""
        return sqlalchemy.create_engine(self.url)

    def get_connection(self):
        """Retourne une connexion psycopg2 pour les insertions en masse (execute_values)."""
        return psycopg2.connect(self.url)


class LocalParquetStorage(ConfigurableResource):
    """
    Ressource de stockage parquet pour le mode local.

    En mode local, le fichier parquet est déjà écrit sur disque par l'asset
    anime_recommendations. Cette ressource ne fait qu'enregistrer l'emplacement.
    """

    output_path: str = "data/recommendations.parquet"

    def deploy(self, local_path: str, logger) -> dict:
        """
        Mode local : ne déploie pas, confirme juste la disponibilité du fichier.

        Args:
            local_path: Chemin local du fichier parquet produit.
            logger: Logger Dagster.

        Returns:
            dict: Métadonnées de statut.
        """
        if not os.path.exists(local_path):
            raise FileNotFoundError(
                f"Fichier parquet introuvable : {local_path}. "
                "L'asset 'anime_recommendations' a-t-il bien tourné ?"
            )

        file_size_mb = os.path.getsize(local_path) / (1024 * 1024)
        logger.info(f"[Local] Parquet disponible : {local_path} ({file_size_mb:.2f} MB)")

        return {
            "status": "local",
            "path": local_path,
            "file_size_mb": round(file_size_mb, 2),
        }


class GitHubReleasesStorage(ConfigurableResource):
    """
    Ressource de stockage parquet pour le mode cloud.

    Téléverse le fichier parquet vers une GitHub Release, ce qui le rend
    accessible publiquement pour l'application Streamlit.
    """

    token: str
    repo: str
    release_tag: str

    def deploy(self, local_path: str, logger) -> dict:
        """
        Upload le fichier parquet local vers la GitHub Release configurée.

        Supprime l'ancien artefact avant l'upload pour éviter les doublons.

        Args:
            local_path: Chemin local du fichier parquet à uploader.
            logger: Logger Dagster.

        Returns:
            dict: Métadonnées incluant l'URL de téléchargement publique.

        Raises:
            FileNotFoundError: Si le fichier local est introuvable.
            requests.HTTPError: En cas d'erreur API GitHub.
        """
        file_name = os.path.basename(local_path)
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }

        # 1. Récupérer l'URL d'upload de la Release
        logger.info(f"Recherche de la Release '{self.release_tag}' sur '{self.repo}'...")
        release_url = f"https://api.github.com/repos/{self.repo}/releases/tags/{self.release_tag}"

        response = requests.get(release_url, headers=headers, timeout=15)
        response.raise_for_status()

        release_data = response.json()
        upload_url = release_data["upload_url"].split("{")[0] + f"?name={file_name}"
        release_id = release_data["id"]

        # 2. Supprimer l'ancien artefact s'il existe
        assets_url = f"https://api.github.com/repos/{self.repo}/releases/{release_id}/assets"
        assets_response = requests.get(assets_url, headers=headers, timeout=15)
        assets_response.raise_for_status()

        for asset in assets_response.json():
            if asset["name"] == file_name:
                logger.info(f"Suppression de l'ancien artefact '{file_name}'...")
                requests.delete(asset["url"], headers=headers, timeout=15)
                break

        # 3. Uploader le nouveau fichier
        logger.info(f"Upload de '{local_path}' vers GitHub Releases...")
        with open(local_path, "rb") as f:
            data = f.read()

        upload_headers = {**headers, "Content-Type": "application/gzip"}
        upload_response = requests.post(upload_url, headers=upload_headers, data=data, timeout=120)
        upload_response.raise_for_status()

        download_url = upload_response.json().get("browser_download_url", "N/A")
        logger.info(f"Upload réussi : {download_url}")

        return {
            "status": "deployed_to_github_release",
            "download_url": download_url,
            "release_tag": self.release_tag,
        }
