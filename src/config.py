# src/config.py
import os
import logging
from dotenv import load_dotenv

# 1. Charger les variables d'env une bonne fois pour toutes
load_dotenv()


ANILIST_API_URL = os.getenv("ANILIST_API_URL")
# Regroupement des paramètres DB pour psycopg2.connect(**DB_PARAMS)
DB_PARAMS = {
    "host": os.getenv("DB_HOST"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
}

# 2. Configurer le logging
# Cela va afficher les logs dans la console avec un format précis : [HEURE] [NIVEAU] Message
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)