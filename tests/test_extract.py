"""Tests de la résilience de l'extraction AniList (rate limiting, retries)."""

import pytest
import requests

from src import extract


class FakeResponse:
    """Réponse HTTP minimale pour simuler l'API AniList."""

    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")


PAYLOAD_OK = {"data": {"Page": {"pageInfo": {"hasNextPage": False}, "media": []}}}


def test_retente_apres_un_rate_limit(monkeypatch):
    """Un HTTP 429 doit déclencher une attente puis une nouvelle tentative."""
    reponses = [
        FakeResponse(429, headers={"Retry-After": "1"}),
        FakeResponse(200, PAYLOAD_OK),
    ]
    attentes = []
    monkeypatch.setattr(extract.time, "sleep", attentes.append)
    monkeypatch.setattr(extract.requests, "post", lambda *a, **kw: reponses.pop(0))

    assert extract.fetch_anilist_page(page=1) == PAYLOAD_OK
    assert attentes, "l'en-tête Retry-After doit être respecté avant de retenter"
    assert reponses == [], "la seconde tentative doit avoir été consommée"


def test_retente_apres_une_erreur_reseau(monkeypatch):
    """Une coupure réseau ponctuelle ne doit pas faire échouer le pipeline."""
    appels = {"n": 0}

    def post_instable(*args, **kwargs):
        appels["n"] += 1
        if appels["n"] == 1:
            raise requests.exceptions.ConnectionError("réseau indisponible")
        return FakeResponse(200, PAYLOAD_OK)

    monkeypatch.setattr(extract.time, "sleep", lambda _: None)
    monkeypatch.setattr(extract.requests, "post", post_instable)

    assert extract.fetch_anilist_page(page=1) == PAYLOAD_OK
    assert appels["n"] == 2


def test_abandonne_apres_le_nombre_max_de_tentatives(monkeypatch):
    """Après épuisement des tentatives, l'erreur remonte pour faire échouer l'asset."""
    monkeypatch.setattr(extract.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        extract.requests,
        "post",
        lambda *a, **kw: (_ for _ in ()).throw(
            requests.exceptions.ConnectionError("réseau indisponible")
        ),
    )

    with pytest.raises(requests.exceptions.ConnectionError):
        extract.fetch_anilist_page(page=1, max_retries=3)


def test_save_page_to_db_ignore_une_page_vide():
    """Aucune requête SQL ne doit partir pour une page sans résultat."""
    assert extract.save_page_to_db(conn=None, animes_data=[]) == 0
