#!/bin/bash
# Runs topics.py to completion, supervised by launchd (see
# com.researchlabfinder.topics.plist) with KeepAlive on non-successful exit
# so an interrupted run (Mac sleep/reboot/crash) auto-resumes rather than
# just staying dead. get_professors_without_topics() already skips anyone
# with an existing ProfessorTopic row, so a restart picks up wherever the
# last run left off instead of redoing finished work.
set -euo pipefail

cd "$(dirname "$0")/.."
LOG_DIR="logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/topics_run_$(date +%Y%m%d_%H%M%S).log"

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

exec /Users/siddanthkarthik/miniconda3/envs/researchlabfinder/bin/python -u -m src.ingestion.topics >> "$LOG_FILE" 2>&1
