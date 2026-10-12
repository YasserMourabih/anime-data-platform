"""
Helpers pour les notebooks Jupyter d'exploration.

Fournit le chargement des vues PostgreSQL et quelques utilitaires d'analyse.
Dépendances supplémentaires : pip install -r requirements-notebooks.txt
"""
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from sqlalchemy import create_engine

from config import DATABASE_URL, logger

# Configuration matplotlib/seaborn
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

def get_engine():
    """Crée un moteur SQLAlchemy vers la base configurée dans .env."""
    return create_engine(DATABASE_URL)

def load_anime_data(engine=None):
    """
    Charge les données d'animes depuis view_anime_basic
    
    Returns:
        pd.DataFrame: DataFrame avec les animes
    """
    if engine is None:
        engine = get_engine()
    
    df = pd.read_sql("SELECT * FROM view_anime_basic", engine)
    
    # Conversion des types
    df['score'] = df['score'].astype('Int64')
    df['episodes'] = df['episodes'].astype('Int64')
    df['start_year'] = df['start_year'].astype('Int64')
    
    logger.info(f"📚 Animes chargés : {df.shape[0]} lignes, {df.shape[1]} colonnes")
    return df

def load_genres_data(engine=None):
    """
    Charge les genres depuis view_anime_genres
    
    Returns:
        pd.DataFrame: DataFrame avec les genres
    """
    if engine is None:
        engine = get_engine()
    
    df = pd.read_sql("SELECT * FROM view_anime_genres", engine)
    logger.info(f"🏷️ Genres chargés : {df.shape[0]} lignes")
    return df

def load_studios_data(engine=None):
    """
    Charge les studios depuis view_anime_studios
    
    Returns:
        pd.DataFrame: DataFrame avec les studios
    """
    if engine is None:
        engine = get_engine()
    
    df = pd.read_sql("SELECT * FROM view_anime_studios", engine)
    logger.info(f"🎬 Studios chargés : {df.shape[0]} lignes")
    return df

def quick_audit(df, name="DataFrame"):
    """
    Affiche un audit rapide d'un DataFrame
    
    Args:
        df (pd.DataFrame): DataFrame à auditer
        name (str): Nom du DataFrame pour l'affichage
    """
    print(f"\n{'='*60}")
    print(f"AUDIT : {name}")
    print(f"{'='*60}")
    print(f"Shape: {df.shape[0]} lignes x {df.shape[1]} colonnes")
    print("\n📊 Premières lignes:")
    print(df.head(3))

def load_all_data(engine=None):
    """
    Charge toutes les données en une seule fois
    
    Returns:
        tuple: (df_anime, df_genres, df_studios)
    """
    if engine is None:
        engine = get_engine()
    
    df_anime = load_anime_data(engine)
    df_genres = load_genres_data(engine)
    df_studios = load_studios_data(engine)
    
    return df_anime, df_genres, df_studios

# Configuration par défaut des graphiques
def setup_plotting():
    """Configure les paramètres par défaut des graphiques"""
    plt.rcParams['figure.figsize'] = (12, 6)
    plt.rcParams['font.size'] = 10
    sns.set_style("whitegrid")
    logger.info("📊 Configuration plotting activée")

# Auto-setup au chargement du module
setup_plotting()
logger.info("Module notebook_helpers chargé")