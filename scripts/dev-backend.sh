#!/usr/bin/env bash
# Local backend development: run Postgres+Redis in Docker, API on the host with reload.
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose up -d postgres redis

cd backend
export POSTGRES_HOST=localhost REDIS_URL=redis://localhost:6379/0
pip install -e ".[dev]" >/dev/null
alembic upgrade head
python -m app.seed
exec uvicorn app.main:app --reload --port 8000
