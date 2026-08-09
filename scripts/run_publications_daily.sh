#!/bin/bash
# Runs publications.py once, meant to be fired daily by launchd
# (see com.researchlabfinder.publications.plist). Each run only pulls
# professors with zero publications so far (get_professors_without_publications)
# and stops itself early once the day's OpenAlex budget looks exhausted
# (ingest_all_publications's consecutive-failure circuit breaker) -- so
# running this daily just makes steady, free, unattended progress on the
# ~192k-professor backlog without ever needing a manual restart or risking
# a runaway retry loop against an empty budget.
set -euo pipefail

cd "$(dirname "$0")/.."
LOG_DIR="logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/publications_daily_$(date +%Y%m%d_%H%M%S).log"

# .env.production (gitignored, not the regular .env local dev/tests use)
# sets DATABASE_URL to Neon -- see docs/ROADMAP.md Phase 6.3. Enrichment
# writes straight to production this way, so there's no separate local
# copy of Institution/Professor/Publication/ResearchTopic data that needs
# re-syncing via pg_dump. A no-op if the file doesn't exist, so this script
# still runs fine against local Postgres if you ever unhook it.
if [ -f .env.production ]; then
    set -a
    source .env.production
    set +a
fi

exec /Users/siddanthkarthik/miniconda3/envs/researchlabfinder/bin/python -u -m src.ingestion.publications >> "$LOG_FILE" 2>&1
