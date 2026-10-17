#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/backend"
export CLIPX_LOCAL_JOBS=1
PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
"$PYTHON_BIN" -m uvicorn clipx.api:app --host 127.0.0.1 --port 8000 &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT INT TERM
cd frontend
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173
