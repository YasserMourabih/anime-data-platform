import sys
import os

# Ajouter le dossier racine au PYTHONPATH
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)


from dagster import Definitions, load_assets_from_modules
import logging

# On importe nos assets
from orchestration import assets

# On charge tous les assets définis dans le module assets.py
all_assets = load_assets_from_modules([assets])

def configure_logging():
    # 1. Récupérer le logger racine de TON application (pas celui de Dagster)
    # Si dans src/config.py tu fais logger = logging.getLogger("anime_platform"), utilise ce nom.
    # Si tu utilises __name__ dans chaque fichier, ils sont sous le logger racine s'ils ne sont pas dans un package.
    # Essayons de configurer le logger racine Python pour commencer.
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Vérifier s'il a déjà des handlers pour éviter les doublons
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    # ASTUCE : Parfois il faut aussi configurer spécifiquement le logger de ton module src
    # Si tes fichiers sont dans src/, le logger s'appelle peut-être 'src.extract' ou juste 'extract'
    logging.getLogger('src').setLevel(logging.INFO)

configure_logging()

defs = Definitions(
    assets=all_assets
    )