"""Tests de la bascule Local/Cloud pilotée par DEPLOYMENT_MODE."""

import importlib

import dotenv
import pytest

import src.config


@pytest.fixture
def recharger_config(monkeypatch):
    """
    Recharge src.config avec un environnement contrôlé.

    load_dotenv est neutralisé pour que les tests ne dépendent pas d'un
    éventuel fichier .env présent sur la machine de développement.
    """
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)

    def _recharger(**variables):
        for cle, valeur in variables.items():
            monkeypatch.setenv(cle, valeur)
        return importlib.reload(src.config)

    yield _recharger

    # Restaure le module dans son état nominal pour les tests suivants
    monkeypatch.undo()
    importlib.reload(src.config)


def test_mode_local_lit_le_parquet_sur_disque(recharger_config):
    config = recharger_config(DEPLOYMENT_MODE="local")

    assert config.PARQUET_SOURCE == str(config.PARQUET_LOCAL_PATH)
    assert config.PARQUET_SOURCE.endswith(".parquet")


def test_mode_cloud_lit_le_parquet_depuis_github_releases(recharger_config):
    config = recharger_config(
        DEPLOYMENT_MODE="cloud",
        PARQUET_URL="https://example.test/recommendations.parquet",
    )

    assert config.PARQUET_SOURCE == "https://example.test/recommendations.parquet"


def test_database_url_est_reconstruite_depuis_les_variables_unitaires(
    recharger_config, monkeypatch
):
    """Compatibilité avec les déploiements qui fournissent DB_HOST, DB_USER, etc."""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    config = recharger_config(
        DB_USER="anime_user",
        DB_PASS="anime_pass",
        DB_HOST="db.example.test",
        DB_PORT="5432",
        DB_NAME="anime_db",
        SSL_MODE="require",
    )

    assert config.DATABASE_URL == (
        "postgresql://anime_user:anime_pass@db.example.test:5432/anime_db?sslmode=require"
    )
