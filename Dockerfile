FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production

# psycopg2 (source) a besoin d'un compilateur et de libpq
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Utilisateur non privilégié ; uploads et logs sont des volumes en écriture
RUN useradd --create-home appuser \
    && mkdir -p uploads logs instance \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# SECRET_KEY et DATABASE_URL sont obligatoires : le démarrage échoue sans eux
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-", "wsgi:app"]
