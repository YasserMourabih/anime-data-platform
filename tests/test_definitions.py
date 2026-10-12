"""Tests du chargement des définitions Dagster (garde-fou anti-régression)."""

from orchestration.definitions import defs


def test_les_trois_assets_du_pipeline_sont_charges():
    cles = {asset.key.to_user_string() for asset in defs.assets}
    assert cles == {"raw_anilist_data", "anime_recommendations", "deploy_recommendations"}


def test_le_job_et_le_schedule_sont_declares():
    assert [job.name for job in defs.jobs] == ["update_anime_platform"]
    assert [schedule.cron_schedule for schedule in defs.schedules] == ["0 3 * * 0"]


def test_les_ressources_attendues_sont_injectees():
    assert set(defs.resources) == {"database", "parquet_storage"}
