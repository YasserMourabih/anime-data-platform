# Anime Data Platform

[![CI](https://github.com/YasserMourabih/anime-data-platform/actions/workflows/ci.yaml/badge.svg)](https://github.com/YasserMourabih/anime-data-platform/actions/workflows/ci.yaml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-3776ab.svg)](https://www.python.org/)
[![Dagster](https://img.shields.io/badge/orchestration-Dagster%201.12-5c3bc6.svg)](https://dagster.io/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Plateforme de recommandation d'animes basée sur l'apprentissage automatique (TF-IDF), avec extraction automatisée depuis l'API [AniList](https://anilist.co/), orchestration via **Dagster** et visualisation via **Streamlit**.

L'ensemble de la stack se lance en une commande (`docker-compose up --build`) : PostgreSQL, le pipeline Dagster et l'application Streamlit.

---

## Fonctionnalités

- **Pipeline d'extraction** : récupération de 25 000+ animes depuis l'API GraphQL AniList avec gestion du rate limiting et retries
- **Système de recommandations** : algorithme TF-IDF pondéré sur genres, tags et synopsis avec détection de franchise
- **Orchestration Dagster** : pipeline en 3 assets avec scheduling hebdomadaire
- **Modularité Local/Cloud** : bascule entre PostgreSQL local et Neon via une seule variable d'environnement
- **Jeu Higher or Lower** : mini-jeu Streamlit pour deviner quel anime a le meilleur score

---

## Architecture

```
anime-data-platform/
├── src/
│   ├── app.py                       # Page d'accueil Streamlit
│   ├── config.py                    # Configuration centralisée (DB, ML, modes)
│   ├── extract.py                   # Extraction AniList → PostgreSQL
│   ├── compute_recommendations.py   # Pipeline ML TF-IDF → Parquet
│   ├── queries.py                   # Requêtes GraphQL et SQL
│   ├── notebook_helpers.py          # Utilitaires pour les notebooks d'exploration
│   ├── db/
│   │   ├── schema.sql               # Table raw_anilist_json
│   │   └── views.sql                # Vues SQL structurées
│   ├── pages/
│   │   ├── 1_higher_lower.py        # Jeu Higher or Lower
│   │   └── 2_anime_recommender.py   # Interface de recommandation
│   └── styles/                      # Fichiers CSS des pages
├── orchestration/
│   ├── assets.py                    # Assets Dagster (ingestion, ML, deploy)
│   ├── definitions.py               # Jobs, schedules et resources
│   └── resources.py                 # DatabaseResource, LocalParquetStorage, GitHubReleasesStorage
├── tests/                           # Tests unitaires (pytest)
├── notebooks/                       # Exploration et prototypage (Jupyter)
├── data/
│   └── recommendations.parquet      # Généré par le pipeline (ignoré par git)
├── .github/workflows/ci.yaml        # Lint, tests, validation Dagster, build Docker
├── Dockerfile                       # Image commune Dagster + Streamlit
├── docker-compose.yml               # Orchestration locale complète
├── requirements.txt                 # Dépendances applicatives
├── requirements-dev.txt             # Dépendances de développement (pytest, ruff)
├── requirements-notebooks.txt       # Dépendances des notebooks (jupyter, matplotlib)
└── .env.example                     # Template de configuration
```

### Flux de données

```
AniList GraphQL API
       ↓
  raw_anilist_data          (Dagster asset — PostgreSQL)
       ↓
  anime_recommendations     (Dagster asset — TF-IDF → Parquet)
       ↓
  deploy_recommendations    (Dagster asset — local: no-op / cloud: GitHub Releases)
       ↓
  Streamlit App             (lit le Parquet et interroge PostgreSQL)
```

La logique métier vit dans `src/` et ne dépend pas de Dagster : les assets ne sont que des enveloppes légères qui injectent la connexion et le logger. Les fonctions restent donc testables et réutilisables hors orchestrateur.

---

## Démarrage rapide (Docker)

### Prérequis

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)

### Lancement

```bash
# 1. Cloner le projet
git clone https://github.com/YasserMourabih/anime-data-platform.git
cd anime-data-platform

# 2. Configurer l'environnement
cp .env.example .env

# 3. Lancer tous les services
docker-compose up --build
```

Les trois services démarrent automatiquement :

| Service    | URL                   | Rôle                          |
|------------|-----------------------|-------------------------------|
| PostgreSQL | `localhost:5433`      | Base de données               |
| Dagster    | http://localhost:3000 | Orchestration du pipeline     |
| Streamlit  | http://localhost:8501 | Application utilisateur       |

Le schéma SQL et les vues sont créés automatiquement au premier démarrage de PostgreSQL.

### Premier lancement

1. Ouvrir l'UI Dagster sur [http://localhost:3000](http://localhost:3000)
2. Lancer le job `update_anime_platform` → **Materialize all**
3. Une fois terminé, l'application Streamlit sur [http://localhost:8501](http://localhost:8501) est alimentée

> Par défaut `.env.example` limite l'extraction à 10 pages (500 animes) pour une démo rapide.
> Augmenter `MAX_PAGES_TO_FETCH` pour un jeu de données complet (500 pages ≈ 25 000 animes, ~30 min avec le rate limiting AniList).

---

## Configuration

Copier `.env.example` en `.env` et adapter selon le mode souhaité.

### Mode local (défaut)

```env
DEPLOYMENT_MODE=local
DATABASE_URL=postgresql://anime_user:anime_pass@localhost:5433/anime_db
ANILIST_API_URL=https://graphql.anilist.co
```

### Mode cloud (Neon + GitHub Releases)

```env
DEPLOYMENT_MODE=cloud
DATABASE_URL=postgresql://<user>:<password>@<host>.neon.tech/<db>?sslmode=require
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
GITHUB_REPO=YourUsername/your-repo
GITHUB_RELEASE_TAG=v1.0.0-data
PARQUET_URL=https://github.com/YourUsername/your-repo/releases/download/v1.0.0-data/recommendations.parquet
```

Seule la variable `DEPLOYMENT_MODE` détermine le comportement de l'ensemble du pipeline et de l'application :

| Composant | Mode `local` | Mode `cloud` |
|---|---|---|
| Base de données | PostgreSQL du docker-compose | PostgreSQL managé (Neon) |
| Stockage du Parquet | `data/recommendations.parquet` | Asset d'une GitHub Release |
| Lecture par Streamlit | Fichier sur disque | URL publique de la Release |

---

## Développement

### Installation hors Docker

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt    # inclut requirements.txt

docker-compose up -d postgres          # juste la base de données
dagster dev -m orchestration.definitions
streamlit run src/app.py
```

### Tests et qualité

```bash
pytest                                        # tests unitaires
ruff check .                                  # lint
dagster definitions validate -m orchestration.definitions
```

Les tests couvrent la préparation textuelle du pipeline ML (nettoyage HTML, normalisation des franchises), la résilience de l'extraction AniList (rate limiting, erreurs réseau, abandon après retries), la bascule Local/Cloud et le chargement des définitions Dagster. Ces trois commandes sont exécutées par l'intégration continue à chaque push.

### Notebooks d'exploration

Les notebooks retracent la phase d'analyse exploratoire et le prototypage du moteur de recommandation. Ils lisent les vues PostgreSQL via `src/notebook_helpers.py` et nécessitent la base alimentée :

```bash
pip install -r requirements-notebooks.txt
jupyter lab notebooks/
```

---

## Algorithme de recommandation

Le système utilise une approche **TF-IDF pondérée** en deux étapes :

| Composante | Source | Poids |
|---|---|---|
| Matrice métadonnées | Genres + tags AniList | 70 % |
| Matrice synopsis | Description textuelle | 30 % |

Les deux matrices sont combinées puis comparées par **similarité cosinus**. Un filtre anti-franchise évite de recommander des suites ou spin-offs de l'anime source : les titres sont normalisés en nom de franchise (`Attack on Titan Season 2` → `attack on titan`) et une seule œuvre par franchise est retenue.

**Résultat** : 10 recommandations par anime, score de similarité de 0 à 1, sur ~5 000 animes (score AniList > 60).

Tous les paramètres (pondérations, seuils, bornes TF-IDF) sont centralisés dans [`src/config.py`](src/config.py).

---

## Technologies

| Couche | Outil |
|---|---|
| Orchestration | Dagster 1.12 |
| Base de données | PostgreSQL 16 (JSONB + vues SQL) |
| Machine Learning | scikit-learn (TF-IDF, similarité cosinus) |
| Format de données | Apache Parquet (PyArrow) |
| Application | Streamlit 1.50 |
| API source | AniList GraphQL |
| Conteneurisation | Docker / Docker Compose |
| CI | GitHub Actions (ruff, pytest, build Docker) |

---

## Statut du projet

La plateforme a tourné en production sur un droplet DigitalOcean, alimentée par une base PostgreSQL managée (Neon) et un déploiement continu via GitHub Actions. Ces ressources cloud ont été décommissionnées.

Le projet est désormais entièrement reproductible en local via Docker Compose, sans aucune dépendance à un service payant. Le workflow de déploiement d'origine est conservé dans [`.github/workflows/deploy_droplet.yaml`](.github/workflows/deploy_droplet.yaml) à titre documentaire, en déclenchement manuel uniquement.

---

## Licence

[MIT](LICENSE)

## Auteur

Yasser Mourabih — [GitHub](https://github.com/YasserMourabih)
