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

exec /Users/siddanthkarthik/miniconda3/envs/researchlabfinder/bin/python -u -m src.ingestion.topics >> "$LOG_FILE" 2>&1
