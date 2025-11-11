"""
Définition des assets Dagster pour le pipeline anime-data-platform.

Ce module contient les assets pour :
- raw_anilist_data : Extraction des données depuis l'API AniList
- anime_recommendations : Calcul des recommandations basées sur TF-IDF
- deploy_recommendations : Déploiement automatique vers GitHub

Les assets sont des wrappers légers autour des fonctions métier,
permettant une séparation claire entre orchestration et logique métier.
"""

from dagster import asset, MaterializeResult, AssetExecutionContext, MetadataValue
import time
import requests
import os
from datetime import datetime
from src.extract import extract_anilist_data
from src.config import MAX_PAGES_TO_FETCH
from src.compute_recommendations import compute_and_save_recommendations


@asset(
    group_name="ingestion",
    description="Extrait les données d'AniList et les charge dans Postgres (raw_anilist_json)"
)
def raw_anilist_data(context: AssetExecutionContext) -> MaterializeResult:
    """
    Asset représentant les données brutes AniList dans PostgreSQL.
    
    Cet asset est un simple wrapper autour de la fonction métier extract_anilist_data.
    La séparation permet de tester la logique métier indépendamment de Dagster.
    """
    context.log.info("🚀 Démarrage de l'extraction AniList via Dagster...")
    
    # Appeler la fonction métier avec le logger Dagster
    metadata = extract_anilist_data(
        max_pages=MAX_PAGES_TO_FETCH,
        delay_between_pages=2,
        logger=context.log
    )
    
    context.log.info(f"✅ Extraction terminée : {metadata['num_records']} animes")
    
    return MaterializeResult(metadata=metadata)


@asset(
    group_name="ml",
    description="Lance le script compute.py pour générer le fichier Parquet des recommandations",
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

@asset(
    deps=[anime_recommendations],  # <--- Il dépend du calcul ML
    group_name="3_deploy",
    description="Upload le fichier Parquet vers GitHub Releases pour Streamlit"
)
def deploy_recommendations(context) -> MaterializeResult:
    """
    Téléverse l'artefact Parquet vers la Release GitHub spécifiée.
    Cela met à jour la "source de vérité" pour l'app Streamlit.
    """
    context.log.info("🚀 Démarrage du déploiement vers GitHub Releases...")

    # --- 1. Charger les secrets (depuis .env) ---
    TOKEN = os.getenv("GITHUB_TOKEN")
    REPO = os.getenv("GITHUB_REPO")
    TAG = os.getenv("GITHUB_RELEASE_TAG")
    FILE_PATH = "data/recommendations.parquet"
    FILE_NAME = "recommendations.parquet"

    if not all([TOKEN, REPO, TAG]):
        context.log.error("Secrets GITHUB_TOKEN, GITHUB_REPO, ou GITHUB_RELEASE_TAG manquants.")
        raise Exception("Variables d'environnement GitHub manquantes.")

    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    # --- 2. Trouver l'URL d'upload pour cette Release ---
    context.log.info(f"Recherche de la Release '{TAG}' sur '{REPO}'...")
    release_url = f"https://api.github.com/repos/{REPO}/releases/tags/{TAG}"
    
    try:
        r = requests.get(release_url, headers=headers)
        r.raise_for_status()  # Lève une exception si erreur (404, 401...)
        
        release_data = r.json()
        upload_url_template = release_data["upload_url"]
        release_id = release_data["id"]

    except requests.exceptions.RequestException as e:
        context.log.error(f"Erreur: Release non trouvée (ou erreur API). {e}")
        raise

    # --- 3. Supprimer l'ancien fichier (robustesse) ---
    context.log.info("Vérification des anciens artefacts...")
    assets_url = f"https://api.github.com/repos/{REPO}/releases/{release_id}/assets"
    
    try:
        r_assets = requests.get(assets_url, headers=headers)
        r_assets.raise_for_status()
        
        for asset_file in r_assets.json():
            if asset_file["name"] == FILE_NAME:
                context.log.warning(f"Suppression de l'ancien fichier '{FILE_NAME}'...")
                requests.delete(asset_file["url"], headers=headers)
                break
    except requests.exceptions.RequestException as e:
        context.log.error(f"Impossible de lister/supprimer les anciens assets : {e}")
        # On continue quand même, l'upload écrasera peut-être l'ancien

    # --- 4. Uploader le nouveau fichier ---
    upload_url = upload_url_template.split("{")[0] + f"?name={FILE_NAME}"
    
    context.log.info(f"📤 Upload de '{FILE_PATH}' vers GitHub...")
    
    try:
        with open(FILE_PATH, 'rb') as f:
            data = f.read()
        
        headers_upload = headers.copy()
        headers_upload["Content-Type"] = "application/gzip"
        
        r_upload = requests.post(upload_url, headers=headers_upload, data=data)
        r_upload.raise_for_status()
        
        download_url = r_upload.json().get("browser_download_url", "N/A")
    
    except FileNotFoundError:
        context.log.error(f"Fichier local non trouvé : {FILE_PATH}. L'asset 'anime_recommendations' a-t-il bien tourné ?")
        raise
    except requests.exceptions.RequestException as e:
        context.log.error(f"Upload échoué: {e.response.json()}")
        raise

    context.log.info(f"✅ Déploiement réussi ! URL: {download_url}")

    return MaterializeResult(
        metadata={
            "status": "deployed_to_github_release",
            "download_url": MetadataValue.url(download_url),
            "release_tag": TAG
        }
    )


# @asset(
#     group_name="deploy",
#     description="Commit et push les recommandations vers GitHub",
#     deps=[anime_recommendations]
# )
# def deploy_recommendations(context: AssetExecutionContext) -> MaterializeResult:
#     """
#     Commit et push le fichier recommendations.json vers GitHub.
    
#     ATTENTION: Cet asset nécessite:
#     - Git configuré avec des credentials valides
#     - Droits d'écriture sur le repository
#     - Être sur une branche appropriée (main, production, etc.)
    
#     Sécurités intégrées:
#     - Vérification de la branche (ne push pas depuis feature branches)
#     - Détection des changements (skip si aucun changement)
#     - Gestion d'erreur complète
#     """
#     json_path = "data/recommendations.json"
    
#     def run_git_cmd(cmd_list: list, error_msg: str) -> str:
#         """Exécute une commande git et retourne le résultat."""
#         result = subprocess.run(
#             cmd_list, 
#             capture_output=True, 
#             text=True,
#             cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Root du projet
#         )
#         if result.returncode != 0:
#             context.log.error(f"{error_msg}: {result.stderr}")
#             raise Exception(f"{error_msg}: {result.stderr}")
        
#         output = result.stdout.strip()
#         if output:
#             context.log.info(f"  └─ {output}")
#         return output

#     context.log.info("🚀 Démarrage du déploiement Git...")

#     try:
#         # 1. Vérifier la branche actuelle
#         current_branch = run_git_cmd(
#             ["git", "branch", "--show-current"], 
#             "Erreur lors de la vérification de la branche"
#         )
#         context.log.info(f"📌 Branche actuelle : {current_branch}")
        
#         # SÉCURITÉ : Ne push que sur des branches autorisées
#         allowed_branches = ["main", "production", "deploy"]
#         if current_branch not in allowed_branches:
#             context.log.warning(
#                 f"⚠️ Déploiement désactivé sur la branche '{current_branch}'. "
#                 f"Branches autorisées : {', '.join(allowed_branches)}"
#             )
#             return MaterializeResult(
#                 metadata={
#                     "status": "skipped_wrong_branch",
#                     "current_branch": current_branch,
#                     "allowed_branches": allowed_branches,
#                     "message": "Déploiement désactivé : branche non-production"
#                 }
#             )

#         # 2. Vérifier si le fichier existe
#         if not os.path.exists(json_path):
#             context.log.error(f"❌ Fichier introuvable : {json_path}")
#             return MaterializeResult(
#                 metadata={
#                     "status": "error_file_not_found",
#                     "file": json_path
#                 }
#             )

#         # 3. Vérifier la taille du fichier
#         file_size_mb = os.path.getsize(json_path) / (1024 * 1024)
#         context.log.info(f"📦 Taille du fichier : {file_size_mb:.2f} MB")
        
#         if file_size_mb > 100:  # GitHub a une limite de 100MB
#             context.log.error(f"❌ Fichier trop volumineux : {file_size_mb:.2f} MB (max: 100 MB)")
#             return MaterializeResult(
#                 metadata={
#                     "status": "error_file_too_large",
#                     "file_size_mb": round(file_size_mb, 2)
#                 }
#             )

#         # 4. Ajouter le fichier au staging
#         context.log.info("📝 Ajout du fichier au staging...")
#         run_git_cmd(["git", "add", json_path], "Erreur git add")

#         # 5. Vérifier s'il y a des changements
#         status = subprocess.run(
#             ["git", "status", "--porcelain", json_path], 
#             capture_output=True, 
#             text=True
#         )
        
#         if not status.stdout.strip():
#             context.log.info("🛑 Aucun changement détecté. Pas de push nécessaire.")
#             return MaterializeResult(
#                 metadata={
#                     "status": "skipped_no_changes",
#                     "branch": current_branch,
#                     "file_size_mb": round(file_size_mb, 2)
#                 }
#             )

#         # 6. Commit avec message descriptif
#         commit_msg = f"data: update recommendations {datetime.now().strftime('%Y-%m-%d %H:%M')} [skip ci]"
#         context.log.info(f"💾 Commit : {commit_msg}")
#         run_git_cmd(["git", "commit", "-m", commit_msg], "Erreur git commit")

#         # 7. Push vers GitHub
#         context.log.info(f"🚢 Push vers origin/{current_branch}...")
#         push_output = run_git_cmd(
#             ["git", "push", "origin", current_branch], 
#             "Erreur git push"
#         )

#         context.log.info("🎉 Déploiement réussi ! Les changements sont maintenant sur GitHub.")
        
#         return MaterializeResult(
#             metadata={
#                 "status": "deployed",
#                 "branch": current_branch,
#                 "file_size_mb": round(file_size_mb, 2),
#                 "commit_message": commit_msg,
#                 "timestamp": datetime.now().isoformat()
#             }
#         )

#     except Exception as e:
#         context.log.error(f"❌ Erreur lors du déploiement : {e}")
#         return MaterializeResult(
#             metadata={
#                 "status": "failed",
#                 "error": str(e),
#                 "timestamp": datetime.now().isoformat()
#             }
#         )