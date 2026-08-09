#!/bin/bash
# Runs enrich_names.py to completion, supervised by launchd (see
# com.researchlabfinder.enrich_names.plist) with KeepAlive on non-successful
# exit so an interrupted run (Mac sleep/reboot/crash) auto-resumes. Unlike
# topics.py/publications.py, this has no "already processed" skip query --
# a restart re-walks every professor with an ORCID id from the top. That's
# still safe (already-cleared ORCID ids no longer match the
# WHERE orcid IS NOT NULL filter, and is_safe_replacement()/the
# `name == current_name` check make re-enriching an already-good name a
# no-op), just not maximally efficient -- acceptable since ORCID's public
# API is free, so the only cost of a restart is time, not money.
set -euo pipefail

cd "$(dirname "$0")/.."
LOG_DIR="logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/enrich_names_run_$(date +%Y%m%d_%H%M%S).log"

# .env.production (gitignored, not the regular .env local dev/tests use)
# sets DATABASE_URL to Neon -- see docs/ROADMAP.md Phase 6.3. Enrichment
# writes straight to production this way, so there's no separate local
# copy of Institution/Professor/Publication/ResearchTopic data that needs
# re-syncing via pg_dump. Silently a no-op if the file doesn't exist, so
# this script still runs fine against local Postgres if you ever unhook it.
if [ -f .env.production ]; then
    set -a
    source .env.production
    set +a
fi

exec /Users/siddanthkarthik/miniconda3/envs/researchlabfinder/bin/python -u -m src.ingestion.enrich_names >> "$LOG_FILE" 2>&1
