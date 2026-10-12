"""Tests des ressources Dagster de stockage du Parquet."""

import logging

import pandas as pd
import pytest

from orchestration.resources import LocalParquetStorage

logger = logging.getLogger(__name__)


def _ecrire_parquet(chemin):
    pd.DataFrame(
        {"source_title": ["Naruto"], "reco_title": ["Bleach"], "score": [0.42]}
    ).to_parquet(chemin, index=False)
    return chemin


def test_deploy_local_retourne_les_metadonnees(tmp_path):
    """En mode local, deploy() ne fait que confirmer la présence du fichier."""
    chemin = _ecrire_parquet(tmp_path / "recommendations.parquet")

    resultat = LocalParquetStorage().deploy(str(chemin), logger)

    assert resultat["status"] == "local"
    assert resultat["path"] == str(chemin)
    assert resultat["file_size_mb"] >= 0


def test_deploy_local_echoue_si_le_parquet_est_absent(tmp_path):
    """Garde-fou : un pipeline qui n'a pas produit son artefact doit échouer."""
    chemin_inexistant = tmp_path / "jamais_genere.parquet"

    with pytest.raises(FileNotFoundError, match="introuvable"):
        LocalParquetStorage().deploy(str(chemin_inexistant), logger)
