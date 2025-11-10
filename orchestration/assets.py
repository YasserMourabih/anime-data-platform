from dagster import asset, MaterializeResult, MetadataValue, AssetExecutionContext
import time
import os
from dotenv import load_dotenv
from src.extract import fetch_anilist_page, save_page_to_db, get_db_connection
from src.config import MAX_PAGES_TO_FETCH
from src.compute_recommendations import compute_and_save_recommendations

load_dotenv()

@asset(
    group_name="ingestion",
    description="Extrait les données d'AniList et les charge dans Postgres (raw_anilist_json)"
)
def raw_anilist_data(context) -> MaterializeResult:
    """
    Cet asset représente la table brute dans PostgreSQL.
    Sa fonction de 'matérialisation' est ton script d'extraction.
    """
    start_time = time.time()
    context.log.info("🚀 Démarrage de l'extraction AniList via Dagster...")
    
    conn = None
    try:
        conn = get_db_connection()
        current_page = 1
        has_next_page = True
        total_inserted = 0

        # Boucle d'extraction
        while has_next_page:
            if MAX_PAGES_TO_FETCH and current_page > MAX_PAGES_TO_FETCH:
                context.log.info(f"🛑 Limite de {MAX_PAGES_TO_FETCH} pages atteinte pour ce run.")
                break

            context.log.info(f"📄 Traitement de la page {current_page}...")
            
            # 1. Extract - on passe le logger Dagster
            api_response = fetch_anilist_page(current_page, logger=context.log)
            data = api_response['data']['Page']
            animes_list = data['media']
            page_info = data['pageInfo']

            # 2. Load - on passe le logger Dagster
            nb_inserted = save_page_to_db(conn, animes_list, logger=context.log)
            total_inserted += nb_inserted
            
            # 3. Prepare next loop
            has_next_page = page_info['hasNextPage']
            current_page += 1
            
            # Respectful delay
            time.sleep(2)  # Petit délai pour ne pas spammer l'API

    except Exception as e:
        context.log.critical(f"🔥 Arrêt inattendu du pipeline : {e}", exc_info=True)
        raise  # Important : on relance l'exception pour que Dagster marque l'asset comme failed
        
    finally:
        if conn:
            conn.close()
            context.log.debug("Connexion BDD fermée.")

    duration = time.time() - start_time
    context.log.info(f"🎉 Pipeline terminé en {duration:.2f}s. Total animes traités : {total_inserted}")

    # Retourner des métadonnées riches pour le monitoring Dagster
    return MaterializeResult(
        metadata={
            "num_records": total_inserted,
            "last_page_fetched": current_page - 1,
            "duration_seconds": round(duration, 2),
            "pages_processed": current_page - 1,
            "avg_records_per_page": round(total_inserted / max(current_page - 1, 1), 2),
            "preview": MetadataValue.md(
                f"""
                ## Extraction AniList réussie ✅
                
                - **Total animes** : {total_inserted}
                - **Pages traitées** : {current_page - 1}
                - **Durée** : {duration:.2f}s
                - **Moyenne** : {total_inserted / max(current_page - 1, 1):.1f} animes/page
                """
            )
        }
    )


@asset(
    group_name="transformation",
    description="Calcule les recommandations d'anime basées sur TF-IDF (genres + tags)",
    deps=[raw_anilist_data]  # Dépend de l'extraction
)
def anime_recommendations(context: AssetExecutionContext) -> MaterializeResult:
    """
    Asset Dagster qui génère des recommandations d'animes.
    
    Cet asset est un simple wrapper autour de la fonction métier compute_and_save_recommendations.
    La séparation permet de tester la logique métier indépendamment de Dagster.
    """
    context.log.info("🧮 Démarrage du calcul des recommandations...")
    
    start_time = time.time()
    
    # Appeler la fonction métier avec le logger Dagster
    metadata = compute_and_save_recommendations(logger=context.log)
    
    # Ajouter le temps d'exécution
    duration = time.time() - start_time
    metadata["duration_seconds"] = round(duration, 2)
    
    context.log.info(f"✅ Recommandations générées en {duration:.2f}s")
    
    return MaterializeResult(metadata=metadata)

