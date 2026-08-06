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

exec /Users/siddanthkarthik/miniconda3/envs/researchlabfinder/bin/python -u -m src.ingestion.enrich_names >> "$LOG_FILE" 2>&1
