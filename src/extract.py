"""
Module d'extraction des données AniList.

Contient la logique métier pour :
1. Paginer l'API GraphQL AniList avec gestion du rate limiting et retries
2. Sauvegarder les données brutes dans PostgreSQL (table raw_anilist_json)

Cette fonction peut être appelée depuis :
- Un asset Dagster (logger Dagster injecté)
- Un script CLI (logger standard Python)
"""

import logging
import time

import psycopg2
import requests
from psycopg2.extras import Json, execute_values

from src.config import ANILIST_API_URL, DATABASE_URL, MAX_PAGES_TO_FETCH, logger
from src.queries import ANILIST_FETCH_PAGE_QUERY, ANILIST_UPSERT_ANIME


def _get_logger(external_logger=None) -> logging.Logger:
    """Retourne le logger externe (Dagster) s'il est fourni, sinon le logger du module."""
    return external_logger if external_logger else logger


def get_db_connection(db_url: str = None):
    """
    Crée et retourne une connexion psycopg2 à la base de données.

    Args:
        db_url: URL de connexion PostgreSQL. Utilise DATABASE_URL de config si None.

    Raises:
        psycopg2.Error: Si la connexion échoue.
    """
    url = db_url or DATABASE_URL
    try:
        return psycopg2.connect(url)
    except psycopg2.Error as e:
        logger.error(f"Impossible de se connecter à la BDD : {e}")
        raise


def fetch_anilist_page(page: int, per_page: int = 50, max_retries: int = 5, logger=None) -> dict:
    """
    Récupère une page de résultats depuis l'API AniList.

    Gère le rate limiting (HTTP 429) avec backoff exponentiel et les erreurs
    réseau avec retry automatique.

    Args:
        page: Numéro de la page à récupérer.
        per_page: Nombre d'animes par page (max 50 selon l'API).
        max_retries: Nombre maximum de tentatives avant abandon.
        logger: Logger optionnel.

    Returns:
        dict: Réponse JSON complète de l'API.

    Raises:
        requests.exceptions.RequestException: Après épuisement des tentatives.
    """
    log = _get_logger(logger)
    variables = {"page": page, "perPage": per_page}
    attempt = 0

    while attempt < max_retries:
        attempt += 1
        try:
            response = requests.post(
                ANILIST_API_URL,
                json={"query": ANILIST_FETCH_PAGE_QUERY, "variables": variables},
                timeout=15,
            )

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                log.warning(
                    f"Rate limit atteint (tentative {attempt}/{max_retries}), "
                    f"attente de {retry_after}s..."
                )
                time.sleep(retry_after + 5)
                continue

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            if attempt >= max_retries:
                log.error(
                    f"Échec définitif après {max_retries} tentatives "
                    f"pour la page {page} : {e}"
                )
                raise
            log.warning(
                f"Erreur réseau (tentative {attempt}/{max_retries}) "
                f"page {page} : {e}. Retry dans 5s..."
            )
            time.sleep(5)

    raise RuntimeError(f"Échec après {max_retries} tentatives (page {page})")


def save_page_to_db(conn, animes_data: list, logger=None) -> int:
    """
    Insère une liste d'objets animes bruts dans la table raw_anilist_json.

    Utilise un upsert (INSERT ... ON CONFLICT) pour gérer les doublons.

    Args:
        conn: Connexion psycopg2 active.
        animes_data: Liste de dicts d'animes provenant de l'API AniList.
        logger: Logger optionnel.

    Returns:
        int: Nombre de lignes insérées/mises à jour.

    Raises:
        psycopg2.Error: En cas d'erreur d'insertion.
    """
    log = _get_logger(logger)

    if not animes_data:
        return 0

    tuples_to_insert = [(anime["id"], Json(anime)) for anime in animes_data]

    try:
        with conn.cursor() as cur:
            execute_values(cur, ANILIST_UPSERT_ANIME, tuples_to_insert)
        conn.commit()
        return len(tuples_to_insert)
    except psycopg2.Error as e:
        conn.rollback()
        log.error(f"Erreur lors de l'insertion en BDD : {e}")
        raise


def extract_anilist_data(
    db_url: str = None,
    max_pages: int = None,
    delay_between_pages: int = 2,
    logger=None,
) -> dict:
    """
    Orchestre l'extraction complète des données AniList vers PostgreSQL.

    Pagine l'API AniList, extrait les données de chaque page et les sauvegarde
    dans la table raw_anilist_json via upsert.

    Args:
        db_url: URL de connexion PostgreSQL. Utilise DATABASE_URL de config si None.
        max_pages: Nombre maximum de pages à extraire. Utilise MAX_PAGES_TO_FETCH si None.
        delay_between_pages: Délai en secondes entre chaque requête API (défaut : 2s).
        logger: Logger optionnel (Dagster ou logging standard).

    Returns:
        dict: Métriques d'exécution (nombre d'animes, pages traitées, durée).

    Raises:
        Exception: Toute erreur critique arrête le pipeline et est propagée.
    """
    log = _get_logger(logger)
    start_time = time.time()
    pages_limit = max_pages if max_pages is not None else MAX_PAGES_TO_FETCH

    log.info("Démarrage du pipeline d'extraction AniList...")

    conn = None
    try:
        conn = get_db_connection(db_url)
        current_page = 1
        has_next_page = True
        total_inserted = 0

        while has_next_page:
            if pages_limit and current_page > pages_limit:
                log.info(f"Limite de {pages_limit} pages atteinte.")
                break

            log.info(f"Traitement de la page {current_page}...")

            api_response = fetch_anilist_page(current_page, logger=logger)
            page_data = api_response["data"]["Page"]
            animes_list = page_data["media"]
            page_info = page_data["pageInfo"]

            nb_inserted = save_page_to_db(conn, animes_list, logger=logger)
            total_inserted += nb_inserted

            has_next_page = page_info["hasNextPage"]
            current_page += 1

            time.sleep(delay_between_pages)

        duration = time.time() - start_time
        pages_processed = current_page - 1
        log.info(
            f"Pipeline terminé en {duration:.2f}s. "
            f"Total animes : {total_inserted} ({pages_processed} pages)"
        )

        return {
            "num_records": total_inserted,
            "pages_processed": pages_processed,
            "duration_seconds": round(duration, 2),
            "avg_records_per_page": round(total_inserted / max(pages_processed, 1), 2),
        }

    except Exception as e:
        log.critical(f"Arrêt inattendu du pipeline : {e}")
        raise

    finally:
        if conn:
            conn.close()
            log.debug("Connexion BDD fermée.")
