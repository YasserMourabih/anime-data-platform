"""
Module pour le calcul et la sauvegarde des recommandations d'animes.

Ce module contient la logique métier pour :
1. Charger les données depuis PostgreSQL (view_anime_basic, view_anime_genres, view_anime_tags)
2. Créer une "soupe" de features combinant genres et tags
3. Calculer la matrice TF-IDF
4. Calculer la similarité cosinus
5. Générer les recommandations pour chaque anime
6. Sauvegarder dans data/recommendations.json

Cette fonction peut être appelée :
- Depuis un asset Dagster (avec logger Dagster)
- Depuis un script CLI (avec logger standard)
- Depuis un notebook (sans logger)
"""

import pandas as pd
import json
import os
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
from dotenv import load_dotenv
import sqlalchemy
from dagster import MetadataValue

load_dotenv()


def clean_html(raw_html):
    """
    Nettoie les balises HTML d'une chaîne de caractères.
    
    Args:
        raw_html: Texte potentiellement avec des balises HTML
        
    Returns:
        str: Texte nettoyé sans balises HTML
    """
    if not raw_html:
        return ''
    
    # Supprimer les balises HTML
    cleanr = re.compile('<.*?>')
    text = re.sub(cleanr, '', raw_html)
    
    # Nettoyer les espaces multiples
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def extract_franchise_name(title):
    """
    Extrait le nom de base d'une franchise en supprimant les variations.
    
    Exemples:
        "Naruto" → "naruto"
        "Naruto: Shippuden" → "naruto"
        "Boruto: Naruto Next Generations" → "naruto"  (détecte "naruto" dans le titre)
        "One Piece" → "one piece"
        "One Piece Film: Red" → "one piece"
        "Attack on Titan Season 2" → "attack on titan"
    
    Args:
        title: Titre de l'anime
        
    Returns:
        str: Nom de franchise normalisé
    """
    if not title:
        return ''
    
    title_lower = title.lower()
    
    # Patterns à supprimer (séquelles, saisons, films, OVA, etc.)
    patterns_to_remove = [
        r'\s*:\s*.*',           # Tout après les deux-points (ex: "Naruto: Shippuden" → "Naruto")
        r'\s+season\s+\d+.*',   # Season + numéro
        r'\s+\d+(st|nd|rd|th)\s+season.*',
        r'\s+part\s+\d+.*',     # Part + numéro
        r'\s+movie.*',          # Movie
        r'\s+film.*',           # Film
        r'\s+ova.*',            # OVA
        r'\s+ona.*',            # ONA
        r'\s+special.*',        # Special
        r'\s+recap.*',          # Recap
        r'\s+\(.*\)$',          # Tout entre parenthèses à la fin
        r'\s+\d+$',             # Numéro seul à la fin (ex: "Naruto 2")
        r'\s+ii$',              # Chiffres romains
        r'\s+iii$',
        r'\s+iv$',
        r'\s+v$',
    ]
    
    # Appliquer tous les patterns
    franchise_name = title_lower
    for pattern in patterns_to_remove:
        franchise_name = re.sub(pattern, '', franchise_name, flags=re.IGNORECASE)
    
    # Nettoyer les espaces multiples et trim
    franchise_name = re.sub(r'\s+', ' ', franchise_name).strip()
    
    # Si c'est trop court après nettoyage, garder au moins 3 premiers mots
    if len(franchise_name) < 3 and title_lower:
        words = title_lower.split()
        franchise_name = ' '.join(words[:min(3, len(words))])
    
    return franchise_name


def compute_and_save_recommendations(
    output_file: str = "data/recommendations.json",
    top_k: int = 10,
    logger=None
) -> dict:
    """
    Calcule les recommandations d'animes basées sur TF-IDF et les sauvegarde dans un fichier JSON.
    
    Args:
        output_file: Chemin du fichier JSON de sortie
        top_k: Nombre de recommandations par anime
        logger: Logger optionnel (Dagster ou logging standard)
        
    Returns:
        dict: Métadonnées pour Dagster (nombre d'animes, taille fichier, etc.)
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
        else:
            print(msg)
    
    # 1. Connexion à la base de données
    log("📊 Connexion à la base de données...")
    db_url = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}?sslmode=require"
    engine = sqlalchemy.create_engine(db_url)
    
    # 2. Chargement des données
    log("⏳ Chargement des données depuis PostgreSQL...")
    df_anime = pd.read_sql("SELECT anime_id, title, description, score FROM view_anime_basic", engine)
    df_genres = pd.read_sql("SELECT anime_id, genre FROM view_anime_genres", engine)
    df_tags = pd.read_sql("SELECT anime_id, tag FROM view_anime_tags", engine)
    
    log(f"✅ {len(df_anime)} animes, {len(df_genres)} genres, {len(df_tags)} tags chargés")
    
    # 2a. Filtrage des animes avec score > 60 (AniList utilise une échelle de 0-100)
    log("🎯 Filtrage des animes avec score > 60...")
    df_anime_before = len(df_anime)
    df_anime = df_anime[df_anime['score'] > 60]
    log(f"   └─ {len(df_anime)}/{df_anime_before} animes conservés (score > 60)")
    
    # 2b. Nettoyage des synopsis (suppression des balises HTML)
    log("🧹 Nettoyage des synopsis...")
    df_anime['description'] = df_anime['description'].apply(clean_html)
    df_anime['description'] = df_anime['description'].fillna('')  # Remplacer NULL par chaîne vide
    
    # 3. Préparation des features
    log("🍳 Préparation de la soupe de features...")
    df_features = pd.concat([
        df_genres.rename(columns={'genre': 'feature_value'})[['anime_id', 'feature_value']],
        df_tags.rename(columns={'tag': 'feature_value'})[['anime_id', 'feature_value']]
    ], ignore_index=True)
    
    # 4. Créer la "soupe" de features par anime
    anime_soup = df_features.groupby('anime_id')['feature_value'].apply(
        lambda x: ' '.join(x.astype(str))
    ).reset_index()
    anime_soup.columns = ['anime_id', 'soup']
    
    # 5. Fusionner avec les titres et descriptions
    df_final = pd.merge(df_anime, anime_soup, on='anime_id', how='left')
    df_final['soup'] = df_final['soup'].fillna('')

    # 5b. ⭐ AJOUT DES SYNOPSIS : On donne un poids x1 car ils sont riches en mots-clés
    synopsis_weight = 1
    tags_genre_weight = 2
    log(f"📝 Intégration des synopsis (poids x{synopsis_weight} et genres x{tags_genre_weight})...")
    df_final['soup'] = (
        (df_final['soup'] + " ") * tags_genre_weight + 
        (df_final['description'] + " ") * synopsis_weight  # Répétition x1 pour garder le poids
    )
    df_final['soup'] = df_final['soup'].str.strip()  # Nettoyer les espaces
    
    # 6. Calcul de la matrice TF-IDF
    log("🤖 Calcul de la matrice TF-IDF...")
    tfidf = TfidfVectorizer(
        stop_words='english',
        ngram_range=(1, 2),
        min_df=10,
        max_df=0.5,
        max_features=1300
        )
    tfidf_matrix = tfidf.fit_transform(df_final['soup'])
    
    log(f"📐 Taille matrice TF-IDF : {tfidf_matrix.shape}")
    
    # 7. Calcul de la similarité cosinus
    log("🔢 Calcul de la matrice de similarité...")
    similarity_matrix = linear_kernel(tfidf_matrix, tfidf_matrix)
    
    # 8. Génération des recommandations
    log("💾 Génération des recommandations...")
    recommendations_dict = {}
    
    for idx, row in df_final.iterrows():
        title = row['title']
        
        # Récupérer les scores de similarité
        sim_scores = list(enumerate(similarity_matrix[idx]))
        sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
        
        # Exclure l'anime lui-même et prendre beaucoup plus de candidats
        # pour avoir assez de diversité après le filtrage anti-doublons
        sim_scores = sim_scores[1:top_k*10]  # On prend 10x plus de candidats pour compenser le filtrage strict
        
        # 🚫 Filtrage anti-doublons robuste (franchises)
        final_recommendations = []
        seen_franchises = set()
        
        # Extraire le nom de franchise de l'anime source
        source_franchise = extract_franchise_name(title)
        seen_franchises.add(source_franchise)
        
        for sim_idx, score in sim_scores:
            candidate_title = df_final.iloc[sim_idx]['title']
            candidate_franchise = extract_franchise_name(candidate_title)
            
            # Vérifier si cette franchise a déjà été vue
            if candidate_franchise in seen_franchises:
                continue
            
            # Vérification supplémentaire: détecter si le nom source est DANS le candidat
            # Ex: "Naruto" est dans "Boruto: Naruto Next Generations"
            if source_franchise in candidate_title.lower() or candidate_franchise in title.lower():
                continue
            
            final_recommendations.append([candidate_title, round(float(score), 3)])
            seen_franchises.add(candidate_franchise)
            
            if len(final_recommendations) >= top_k:
                break
        
        recommendations_dict[title] = final_recommendations
        
        # Log progression tous les 1000 animes
        if (idx + 1) % 1000 == 0:
            log(f"   � {idx + 1}/{len(df_final)} animes traités...")
    
    # 9. Sauvegarde dans un fichier JSON
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    log(f"📦 Sauvegarde dans {output_file}...")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(recommendations_dict, f, indent=2, ensure_ascii=False)
    
    log("✅ Recommandations générées avec succès !")
    
    # 10. Calcul des métadonnées pour Dagster
    total_animes = len(recommendations_dict)
    avg_recommendations = sum(len(v) for v in recommendations_dict.values()) / total_animes if total_animes > 0 else 0
    file_size_mb = os.path.getsize(output_file) / (1024 * 1024)
    
    metadata = {
        "total_animes": total_animes,
        "avg_recommendations_per_anime": round(avg_recommendations, 2),
        "tfidf_matrix_shape": f"{tfidf_matrix.shape[0]} x {tfidf_matrix.shape[1]}",
        "output_file": output_file,
        "file_size_mb": round(file_size_mb, 2),
        "preview": MetadataValue.md(
            f"""
            ## Recommandations générées ✅
            
            - **Total animes** : {total_animes:,}
            - **Moyenne recommandations/anime** : {avg_recommendations:.1f}
            - **Matrice TF-IDF** : {tfidf_matrix.shape[0]:,} x {tfidf_matrix.shape[1]:,}
            - **Taille fichier** : {file_size_mb:.2f} MB
            - **Fichier** : `{output_file}`
            """
        )
    }
    
    return metadata


if __name__ == "__main__":
    """Permet d'exécuter le script directement depuis la ligne de commande."""
    import logging
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    print("🚀 Démarrage du calcul des recommandations...")
    result = compute_and_save_recommendations(logger=logger)
    print(f"\n📊 Résultats:")
    for key, value in result.items():
        if key != "preview":
            print(f"  - {key}: {value}")