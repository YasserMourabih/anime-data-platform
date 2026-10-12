FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DAGSTER_HOME=/app/dagster_home

# Installer les dépendances en premier pour profiter du cache Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code source
COPY . .

# DAGSTER_HOME doit exister : il contient l'instance Dagster (runs, schedules)
RUN mkdir -p "$DAGSTER_HOME" data

EXPOSE 3000 8501

# Commande par défaut : Dagster (surchargée par docker-compose pour Streamlit)
CMD ["dagster", "dev", "-h", "0.0.0.0", "-p", "3000", "-m", "orchestration.definitions"]
