# 🎌 Anime Data Platform

Plateforme de recommandation d'animes basée sur l'apprentissage automatique (TF-IDF), avec extraction automatisée des données depuis [AniList](https://anilist.co/) et orchestration via Dagster.

## 📋 Fonctionnalités

- **🔄 Pipeline d'extraction** : Récupération automatisée de 25 000+ animes depuis l'API AniList
- **🧠 Système de recommandations** : Algorithme TF-IDF pondéré (genres, tags, synopsis)
- **🎮 Jeu Higher or Lower** : Interface interactive Streamlit pour deviner les scores d'animes
- **⚙️ Orchestration Dagster** : Pipeline automatisé avec scheduling hebdomadaire
- **💾 Base PostgreSQL** : Stockage structuré avec vues SQL optimisées

## 🏗️ Architecture

```
anime-data-platform/
├── src/
│   ├── app.py                      # Application Streamlit principale
│   ├── extract.py                  # Logique d'extraction AniList
│   ├── compute_recommendations.py  # Calcul des recommandations ML
│   ├── config.py                   # Configuration centralisée
│   ├── queries.py                  # Requêtes GraphQL/SQL
│   ├── db/
│   │   ├── schema.sql             # Schéma de base de données
│   │   └── views.sql              # Vues SQL (anime_basic, genres, tags)
│   └── pages/
│       ├── 1_higher_lower.py      # Jeu Higher or Lower
│       └── higher_lower_styles.css # Styles CSS du jeu
├── orchestration/
│   ├── assets.py                   # Assets Dagster (extraction, ML, deploy)
│   ├── definitions.py             # Définition des jobs et schedules
│   └── resources.py               # Ressources Dagster
├── data/
│   └── recommendations.json       # Fichier JSON des recommandations
├── notebooks/                      # Notebooks Jupyter d'exploration
├── requirements.txt               # Dépendances Python
└── .env.example                   # Template variables d'environnement

```

## 🚀 Installation

### Prérequis

- Python 3.11+
- PostgreSQL (ou instance Neon)
- Compte AniList (optionnel pour rate limits étendus)

### Setup

1. **Cloner le repository**
```bash
git clone https://github.com/YasserMourabih/anime-data-platform.git
cd anime-data-platform
```

2. **Créer un environnement virtuel**
```bash
python -m venv venv
source venv/bin/activate  # Sur macOS/Linux
# ou venv\Scripts\activate sur Windows
```

3. **Installer les dépendances**
```bash
pip install -r requirements.txt
```

4. **Configurer les variables d'environnement**
```bash
cp .env.example .env
# Éditer .env avec vos credentials PostgreSQL
```

5. **Initialiser la base de données**
```bash
psql -h <DB_HOST> -U <DB_USER> -d <DB_NAME> -f src/db/schema.sql
psql -h <DB_HOST> -U <DB_USER> -d <DB_NAME> -f src/db/views.sql
```

## 📊 Utilisation

### Extraction des données AniList

```bash
python -m src.extract
```

### Calcul des recommandations

```bash
python -m src.compute_recommendations
```

### Lancer l'application Streamlit

```bash
streamlit run src/app.py
```

### Orchestration Dagster

```bash
dagster dev -f orchestration/definitions.py
```

Puis ouvrir [http://localhost:3000](http://localhost:3000)

## 🎯 Algorithme de Recommandation

Le système utilise une approche hybride basée sur **TF-IDF** avec pondération :

1. **Extraction de features** : Genres, tags, synopsis
2. **Vectorisation séparée** :
   - Matrice Meta (genres + tags) : 70% du poids
   - Matrice Synopsis : 30% du poids
3. **Similarité cosinus** : Comparaison entre tous les animes
4. **Filtrage anti-doublons** : Détection automatique des franchises (ex: "Naruto" vs "Naruto Shippuden")

**Résultat** : ~10 recommandations par anime, avec un score de similarité de 0 à 1

## 🎮 Jeu Higher or Lower

Interface interactive permettant de deviner si un anime a un score plus haut ou plus bas qu'un autre.

**Features** :
- ✨ Animations CSS fluides
- 🖼️ Images de couverture des animes
- 📊 Tracking du score et des séries
- 🎨 Design moderne avec gradients

## 🔧 Technologies

- **Backend** : Python, PostgreSQL
- **ML** : Scikit-learn (TF-IDF, Cosine Similarity)
- **Orchestration** : Dagster
- **Frontend** : Streamlit
- **API** : AniList GraphQL
- **Cloud** : Neon (PostgreSQL serverless)

## 📝 TODO

Voir [TODO.md](TODO.md) pour la roadmap complète.

## 📄 Licence

MIT

## 👤 Auteur

Yasser Mourabih - [GitHub](https://github.com/YasserMourabih)