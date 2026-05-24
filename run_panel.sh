#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"
source .venv/bin/activate

JOB_PANEL_HOST="${JOB_PANEL_HOST:-127.0.0.1}"
JOB_PANEL_PORT="${JOB_PANEL_PORT:-8781}"
JOB_PANEL_DATA_DIR="${JOB_PANEL_DATA_DIR:-$PROJECT_DIR/data/output}"
JOB_PANEL_PANEL_DIR="${JOB_PANEL_PANEL_DIR:-$PROJECT_DIR/panel}"
JOB_PANEL_STATUS_FILE="${JOB_PANEL_STATUS_FILE:-$PROJECT_DIR/data/status/job_status.json}"
# Auth is resolved by job_panel_server.py from:
# JOB_HUNTER_PANEL_USER, JOB_HUNTER_PANEL_PASSWORD, JOB_HUNTER_PANEL_AUTH_DISABLED

exec python job_panel_server.py \
  --host "${JOB_PANEL_HOST}" \
  --port "${JOB_PANEL_PORT}" \
  --data-dir "${JOB_PANEL_DATA_DIR}" \
  --panel-dir "${JOB_PANEL_PANEL_DIR}" \
  --status-file "${JOB_PANEL_STATUS_FILE}"
