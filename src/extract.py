"""
Module pour l'extraction des données AniList.

Ce module contient la logique métier pour :
1. Fetcher les pages de l'API AniList avec gestion du rate limiting
2. Sauvegarder les données dans PostgreSQL (table raw_anilist_json)
3. Gérer les retries en cas d'erreur réseau ou serveur

Cette fonction peut être appelée :
- Depuis un asset Dagster (avec logger Dagster)
- Depuis un script CLI (avec logger standard)
- Depuis un notebook (sans logger)
"""

import time
import requests
import psycopg2
from psycopg2.extras import execute_values, Json
from dagster import MetadataValue
from src.config import DB_PARAMS, ANILIST_API_URL, MAX_PAGES_TO_FETCH, logger
from src.queries import ANILIST_FETCH_PAGE_QUERY, ANILIST_UPSERT_ANIME

# Vérification basique de la config (déjà chargée par config.py)
if not all(DB_PARAMS.values()) or not ANILIST_API_URL:
    raise EnvironmentError("❌ Missing environment variables. Check your .env file")

def get_db_connection():
    """Crée et retourne une connexion à la base de données."""
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        return conn
    except psycopg2.Error as e:
        logger.error(f"❌ Impossible de se connecter à la BDD : {e}")
        raise  # On relance l'exception pour arrêter le script si la BDD est down

def fetch_anilist_page(page: int, per_page: int = 50, max_retries: int = 5, logger=None) -> dict:
    """
    Récupère une page de résultats depuis l'API AniList.
    Gère le rate limiting (429) avec retry limité.
    """
    # Utiliser le logger passé en paramètre ou celui par défaut de config.py
    log = logger if logger else globals()['logger']
    
    variables = {'page': page, 'perPage': per_page}
    attempt = 0
    while attempt < max_retries: # Boucle de retry pour le rate limiting
        attempt += 1
        try:
            response = requests.post(
                ANILIST_API_URL,
                json={'query': ANILIST_FETCH_PAGE_QUERY, 'variables': variables}, 
                timeout=15
            )
            
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                log.warning(f"⏳ Rate limit atteint (tentative {attempt}/{max_retries}), attendre {retry_after}s... ")
                time.sleep(retry_after + 5) # On ajoute une petite marge de sécurité
                continue # On réessaie la même requête

            response.raise_for_status() # Lève une exception pour les autres codes d'erreur (5xx, 404...)
            return response.json()

        except requests.exceptions.RequestException as e:
            if attempt >= max_retries:
                log.error(
                    f"❌ Échec définitif après {max_retries} tentatives "
                    f"pour la page {page} : {e}"
                )
                raise
            else:
                log.warning(
                    f"⚠️ Erreur réseau (tentative {attempt}/{max_retries}) "
                    f"page {page} : {e}. Retry dans 5s..."
                )
                time.sleep(5)
                continue

    # Ne devrait jamais arriver (raise dans le except ci-dessus)
    raise RuntimeError(f"Échec après {max_retries} tentatives (page {page})")

def save_page_to_db(conn, animes_data: list, logger=None) -> int:
    """
    Insère une liste d'objets animes bruts dans la table raw_anilist_json.
    Utilise une connexion existante.
    """
    # Utiliser le logger passé en paramètre ou celui par défaut de config.py
    log = logger if logger else globals()['logger']
    
    if not animes_data:
        return 0

    # Préparation des données pour execute_values
    tuples_to_insert = [(anime['id'], Json(anime)) for anime in animes_data]
    
    try:
        with conn.cursor() as cur:
            execute_values(cur, ANILIST_UPSERT_ANIME, tuples_to_insert)
        conn.commit()
        return len(tuples_to_insert)
    except psycopg2.Error as e:
        conn.rollback() # Important : on annule la transaction en cas d'erreur
        log.error(f"❌ Erreur lors de l'insertion en BDD : {e}")
        raise

def main():
    """
    Fonction principale d'orchestration (legacy pour rétro-compatibilité).
    Utilise maintenant extract_anilist_data() en interne.
    """
    result = extract_anilist_data(logger=logger)
    logger.info(f"✅ Extraction terminée : {result['num_records']} animes en {result['duration_seconds']:.2f}s")


def extract_anilist_data(
    max_pages: int = None,
    delay_between_pages: int = 2,
    logger=None
) -> dict:
    """
    Fonction principale d'extraction des données AniList.
    
    Args:
        max_pages: Nombre max de pages à extraire (None = utiliser MAX_PAGES_TO_FETCH de config)
        delay_between_pages: Délai en secondes entre chaque page (défaut: 2s)
        logger: Logger optionnel (Dagster ou logging standard)
        
    Returns:
        dict: Métadonnées pour Dagster (nombre d'animes, pages, durée, etc.)
    """
    
    def log(msg, level="info"):
        """Helper pour logger avec ou sans logger externe."""
        if logger:
            if level == "info":
                logger.info(msg)
            elif level == "warning":
                logger.warning(msg)
            elif level == "error":
                logger.error(msg)
            elif level == "critical":
                logger.critical(msg)
            elif level == "debug":
                logger.debug(msg)
        else:
            print(msg)
    
    start_time = time.time()
    log("🚀 Démarrage du pipeline d'extraction AniList")

    # Utiliser max_pages si fourni, sinon MAX_PAGES_TO_FETCH de config
    pages_limit = max_pages if max_pages is not None else MAX_PAGES_TO_FETCH

    conn = None
    try:
        conn = get_db_connection()
        current_page = 1
        has_next_page = True
        total_inserted = 0

        # Boucle d'extraction
        while has_next_page:
            if pages_limit and current_page > pages_limit:
                log(f"🛑 Limite de {pages_limit} pages atteinte pour ce run.")
                break

            log(f"📄 Traitement de la page {current_page}...")
            
            # 1. Extract
            api_response = fetch_anilist_page(current_page, logger=logger)
            data = api_response['data']['Page']
            animes_list = data['media']
            page_info = data['pageInfo']

            # 2. Load
            nb_inserted = save_page_to_db(conn, animes_list, logger=logger)
            total_inserted += nb_inserted
            
            # 3. Prepare next loop
            has_next_page = page_info['hasNextPage']
            current_page += 1
            
            # Respectful delay
            time.sleep(delay_between_pages)

        duration = time.time() - start_time
        log(f"🎉 Pipeline terminé en {duration:.2f}s. Total animes traités : {total_inserted}")
        
        # Métadonnées pour Dagster
        metadata = {
            "num_records": total_inserted,
            "last_page_fetched": current_page - 1,
            "duration_seconds": round(duration, 2),
            "pages_processed": current_page - 1,
            "avg_records_per_page": round(total_inserted / max(current_page - 1, 1), 2),
            "preview": MetadataValue.md(
                f"""
                ## Extraction AniList réussie ✅
                
                - **Total animes** : {total_inserted:,}
                - **Pages traitées** : {current_page - 1}
                - **Durée** : {duration:.2f}s
                - **Moyenne** : {total_inserted / max(current_page - 1, 1):.1f} animes/page
                """
            )
        }
        
        return metadata

    except Exception as e:
        log(f"🔥 Arrêt inattendu du pipeline : {e}", level="critical")
        raise
        
    finally:
        if conn:
            conn.close()
            log("Connexion BDD fermée.", level="debug")

if __name__ == "__main__":
    """Permet d'exécuter le script directement depuis la ligne de commande."""
    import logging
    
    # Le logger est déjà configuré dans config.py, mais on peut le reconfigurer si besoin
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    cli_logger = logging.getLogger(__name__)
    
    print("🚀 Démarrage de l'extraction AniList...")
    result = extract_anilist_data(logger=cli_logger)
    print(f"\n📊 Résultats:")
    for key, value in result.items():
        if key != "preview":
            print(f"  - {key}: {value}")