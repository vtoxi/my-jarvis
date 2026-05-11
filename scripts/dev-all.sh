#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/apps/api"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -e ".[dev]"

echo "Starting FastAPI on http://127.0.0.1:8000 (background)…"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT

sleep 1
cd "$ROOT"
echo "Run desktop in another terminal: npm install && npm run dev"
echo "Or press Ctrl+C to stop the API."
wait "$API_PID"
