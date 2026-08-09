# Single container serving /api/* and the static frontend from one origin
# (see docs/ROADMAP.md Phase 6.2) -- no separate static host, no CDN needed
# at this dataset's size.
FROM python:3.12-slim

WORKDIR /app

# psycopg[binary] bundles libpq itself, so no libpq-dev/build-essential is
# needed here -- just CA certs, since the managed Postgres connection (Neon)
# is TLS.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# src/ingestion isn't imported by the web app (see requirements.txt's
# comment on pyalex/openpyxl) but src/database.py and the ingestion package
# share the src/ namespace, so the whole directory is copied rather than
# cherry-picked to avoid import-path surprises.
COPY backend/ backend/
COPY src/ src/
COPY database/ database/
COPY frontend/ frontend/

ENV PORT=8000
EXPOSE 8000

# Migrations run at container start rather than as a separate release step
# -- Render's preDeployCommand requires a paid plan, and this dataset's
# free-tier deploy can't use it. database/migrate.py is idempotent (tracks
# applied versions in schema_migrations, every migration file uses
# CREATE TABLE IF NOT EXISTS/similar), so re-running it on every boot --
# including free-tier cold starts after the instance sleeps -- is safe and
# adds a sub-second check, not a real cost.
CMD ["sh", "-c", "python -m database.migrate && uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
