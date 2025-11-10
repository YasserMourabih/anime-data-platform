import time
import requests
import psycopg2
from psycopg2.extras import execute_values, Json
from src.config import DB_PARAMS, ANILIST_API_URL, MAX_PAGES_TO_FETCH, logger #On importe depuis src/config.py
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
    """Fonction principale d'orchestration."""
    start_time = time.time()
    logger.info("🚀 Démarrage du pipeline d'extraction AniList")

    conn = None
    try:
        conn = get_db_connection()
        current_page = 1
        has_next_page = True
        total_inserted = 0

        # Sécurité pendant le dev : limiter le nombre de pages pour tester vite
        # Mets cette valeur à None ou très haut quand tu veux tout récupérer
        while has_next_page:
            if MAX_PAGES_TO_FETCH and current_page > MAX_PAGES_TO_FETCH:
                logger.info(f"🛑 Limite de {MAX_PAGES_TO_FETCH} pages atteinte pour ce run.")
                break

            logger.info(f"📄 Traitement de la page {current_page}...")
            
            # 1. Extract
            api_response = fetch_anilist_page(current_page)
            data = api_response['data']['Page']
            animes_list = data['media']
            page_info = data['pageInfo']

            # 2. Load
            nb_inserted = save_page_to_db(conn, animes_list)
            total_inserted += nb_inserted
            
            # 3. Prepare next loop
            has_next_page = page_info['hasNextPage']
            current_page += 1
            
            # Respectful delay
            time.sleep(2) # Petit délai pour ne pas spammer l'API même si on est sous la limite (1s = API normale / 2s = API degradée)

    except Exception as e:
        logger.critical("🔥 Arrêt inattendu du pipeline.", exc_info=True)
    finally:
        if conn:
            conn.close()
            logger.debug("Connexion BDD fermée.")

    duration = time.time() - start_time
    logger.info(f"🎉 Pipeline terminé en {duration:.2f}s. Total animes traités : {total_inserted}")

if __name__ == "__main__":
    main()