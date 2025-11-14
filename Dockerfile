# Dockerfile

# --- ÉTAPE 1: LE PLAN DE TRAVAIL ---
# On part d'une "boîte" qui contient déjà Python 3.11 pré-installé.
# "-slim" est une version légère, parfaite pour la production.
FROM python:3.11-slim

# --- ÉTAPE 2: LE DOSSIER DE TRAVAIL ---
# On crée un dossier /app à l'intérieur de la boîte
# et on se place dedans.
WORKDIR /app

# --- ÉTAPE 3: INSTALLATION DES DÉPENDANCES ---
# C'est l'étape la plus importante pour l'optimisation.
# On copie SEULEMENT le fichier requirements...
COPY requirements_dagster.txt .

# ... et on installe les dépendances MAINTENANT.
# Docker met cette étape en cache. Si tu changes ton code (ex: app.py)
# mais pas tes requirements, Docker n'aura pas à tout réinstaller !
# C'est une "couche" (layer) d'image.
# On force la version CPU pour éviter les bibliothèques GPU inutiles
# Installe PyTorch en version CPU-only
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
# Installe le reste des dépendances
RUN pip install --no-cache-dir -r requirements_dagster.txt

# --- ÉTAPE 4: COPIE DU CODE SOURCE ---
# Maintenant que les dépendances sont installées, on copie
# tout le reste de notre code (src/, orchestration/, etc.) dans la boîte.
# Le "." signifie "tout ce qui est dans mon dossier local"
# (sauf ce qui est dans .dockerignore)
COPY . .

# --- ÉTAPE 5: EXPOSITION (Pour plus tard) ---
# On dit à Docker que notre service Dagster tournera sur le port 3000
EXPOSE 3000

# --- ÉTAPE 6: LA COMMANDE DE DÉMARRAGE ---
# Qu'est-ce que cette boîte doit faire quand on la lance ?
# Elle doit lancer l'interface web de Dagster !
CMD ["dagster", "dev", "-h", "0.0.0.0", "-p", "3000", "-m", "orchestration.definitions"]