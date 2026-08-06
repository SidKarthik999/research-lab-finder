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

exec /Users/siddanthkarthik/miniconda3/envs/researchlabfinder/bin/python -u -m src.ingestion.publications >> "$LOG_FILE" 2>&1
