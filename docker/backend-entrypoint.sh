#!/bin/sh
# Entrypoint for the backend image. Modes:
#   api        run migrations + seed, then serve the API
#   worker     Celery worker (lifecycle + billing queues)
#   scheduler  Celery beat
set -e

case "$1" in
  api)
    echo "Running database migrations..."
    alembic upgrade head
    echo "Seeding defaults (idempotent)..."
    python -m app.seed
    echo "Starting API..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
    ;;
  worker)
    exec celery -A app.workers.celery_app worker \
      --loglevel=INFO --queues=default,billing --concurrency=4
    ;;
  scheduler)
    exec celery -A app.workers.celery_app beat --loglevel=INFO
    ;;
  *)
    exec "$@"
    ;;
esac
