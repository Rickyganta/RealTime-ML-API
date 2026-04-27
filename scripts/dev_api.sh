#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f ".venv/bin/python" ]]; then
  echo "Missing venv: create it first: python3.11 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt" >&2
  exit 1
fi

# Load local env if present (LOADTEST_BYPASS_TOKEN lives here in dev)
if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

# Local dev safety: .env in this repo often uses docker-compose service hostnames
# (postgres/redis). Those hostnames do not resolve on your laptop unless Docker networking provides them.
# When running the API directly on macOS, rewrite to localhost.
_postgres_url="${POSTGRES_URL:-}"
if [[ -n "$_postgres_url" ]]; then
  # postgres://user:pass@postgres:port/db -> @localhost:port
  if [[ "$_postgres_url" == *"@postgres:"* ]]; then
    export POSTGRES_URL="${_postgres_url/@postgres:/@localhost:}"
  fi
fi

_redis_url="${REDIS_URL:-}"
if [[ -n "$_redis_url" ]]; then
  if [[ "$_redis_url" == *"//redis:"* ]]; then
    # redis://redis:6379/0 -> redis://localhost:6379/0
    export REDIS_URL="${_redis_url//\/\/redis:\//\/\/localhost:}"
  fi
fi

export PYTHONPATH="${PYTHONPATH:-.}"

exec .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
