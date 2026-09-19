#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
VENV="$BACKEND_DIR/.venv"
command -v python >/dev/null || { echo "Python is required."; exit 1; }
command -v cloudflared >/dev/null || { echo "cloudflared is required. Install it first."; exit 1; }
[[ -d "$VENV" ]] || python -m venv "$VENV"
source "$VENV/bin/activate"
python -m pip install -q -r "$BACKEND_DIR/requirements.txt"
if [[ -f "$ROOT_DIR/.env.local.backend" ]]; then set -a; source "$ROOT_DIR/.env.local.backend"; set +a; fi
export PYTHONPATH="$BACKEND_DIR"
export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:3000,https://authentiq-integrity.vercel.app}"
cleanup() { [[ -n "${API_PID:-}" ]] && kill "$API_PID" 2>/dev/null || true; [[ -n "${TUNNEL_PID:-}" ]] && kill "$TUNNEL_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
cd "$BACKEND_DIR"
python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" & API_PID=$!
sleep 2
if [[ -n "${CLOUDFLARE_TUNNEL_NAME:-}" ]]; then
  cloudflared tunnel run "$CLOUDFLARE_TUNNEL_NAME" & TUNNEL_PID=$!
  echo "Stable AuthentiQ tunnel started: ${AUTHENTIQ_API_URL:-configure your hostname}"
else
  cloudflared tunnel --url "http://127.0.0.1:${PORT:-8000}" 2>&1 | tee /tmp/authentiq-cloudflare.log & TUNNEL_PID=$!
  sleep 3
  echo "Temporary tunnel URL is in /tmp/authentiq-cloudflare.log"
fi
echo "AuthentiQ backend is running. Press Ctrl+C to stop everything."
wait "$API_PID"
