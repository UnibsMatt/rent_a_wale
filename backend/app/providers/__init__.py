"""Provider registry: config-driven selection of the orchestrator backend."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.providers.base import DeploymentProvider


@lru_cache
def get_provider() -> DeploymentProvider:
    if settings.deployment_provider == "docker":
        from app.providers.docker.provider import DockerProvider

        return DockerProvider()
    raise ValueError(f"Unknown deployment provider: {settings.deployment_provider}")
