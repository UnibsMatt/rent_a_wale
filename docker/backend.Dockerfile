# Backend image: FastAPI API, Celery worker, and beat scheduler all use this image
# with different commands.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/app

COPY backend/pyproject.toml ./
# Install dependencies first for layer caching; hatchling needs the package present,
# so create a stub, install, then overwrite with the real sources.
RUN mkdir -p app && touch app/__init__.py && pip install .

COPY backend/ ./

COPY docker/backend-entrypoint.sh /usr/local/bin/backend-entrypoint.sh
RUN chmod +x /usr/local/bin/backend-entrypoint.sh

# NOTE: the API and worker containers mount /var/run/docker.sock and therefore run as
# root inside their container. This is inherent to the single-VM Docker-socket design;
# see docs/architecture.md ADR-6 for the trade-off and hardening path.
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -fsS http://localhost:8000/health || exit 1

ENTRYPOINT ["backend-entrypoint.sh"]
CMD ["api"]
