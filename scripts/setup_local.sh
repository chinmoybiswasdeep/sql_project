#!/usr/bin/env bash
# Local setup without Docker.
#  * Python 3.11+ virtual environment in .venv with project dependencies
#  * Optionally a project-local PostgreSQL 16 cluster in .pgdata on port 5433
#    (requires initdb/pg_ctl on PATH; e.g. `micromamba create -p .venv -c conda-forge
#    python=3.12 postgresql=16` provides both, which is how this repo was developed)
# Usage: scripts/setup_local.sh [--with-postgres]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -x .venv/bin/python ]]; then
  PYBIN="$(command -v python3.12 || command -v python3.11 || true)"
  [[ -n "$PYBIN" ]] || { echo "Python 3.11+ not found" >&2; exit 1; }
  "$PYBIN" -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip >/dev/null
.venv/bin/python -m pip install -e ".[dev]"
[[ -f .env ]] || cp .env.example .env

if [[ "${1:-}" == "--with-postgres" ]]; then
  export PATH="$ROOT/.venv/bin:$PATH"
  command -v initdb >/dev/null || { echo "initdb not found; install PostgreSQL 16" >&2; exit 1; }
  if [[ ! -d .pgdata ]]; then
    initdb -D .pgdata -U hi_admin --auth=trust -E UTF8 --locale=C >/dev/null
    cat >> .pgdata/postgresql.conf <<'CONF'
port = 5433
listen_addresses = 'localhost'
shared_buffers = 512MB
work_mem = 64MB
maintenance_work_mem = 256MB
CONF
  fi
  pg_ctl -D .pgdata -l .pgdata/server.log status >/dev/null 2>&1 || pg_ctl -D .pgdata -l .pgdata/server.log start -w
  createdb -h localhost -p 5433 -U hi_admin hospital_intel 2>/dev/null || true
  echo "PostgreSQL running on localhost:5433 (db hospital_intel, user hi_admin)"
fi
echo "Setup complete. Next: scripts/run_pipeline.sh"
