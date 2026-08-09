# Single container serving /api/* and the static frontend from one origin
# (see docs/ROADMAP.md Phase 6.2) -- no separate static host, no CDN needed
# at this dataset's size. Deploy = build this image -> run
# `python -m database.migrate` as a release step -> start uvicorn.
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

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
