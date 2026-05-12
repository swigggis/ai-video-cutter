#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ ! -d "venv" ]]; then
  echo "[ERROR] Python venv fehlt. Bitte erst README folgen und venv anlegen."
  exit 1
fi

if [[ -f ".env" ]]; then
  # shellcheck disable=SC1091
  source .env
fi

# shellcheck disable=SC1091
source venv/bin/activate

BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

echo "[INFO] Starte Backend auf ${BACKEND_HOST}:${BACKEND_PORT}"
uvicorn backend.app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" &
BACKEND_PID=$!

cleanup() {
  echo "[INFO] Stoppe Backend ${BACKEND_PID}"
  kill "$BACKEND_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

echo "[INFO] Starte Frontend auf 0.0.0.0:${FRONTEND_PORT}"
npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT"