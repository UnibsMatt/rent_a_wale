"""Application configuration.

All configuration comes from the environment (12-factor). In production mode the
application refuses to start while any CHANGE_ME sentinel is present.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_SENTINEL = "CHANGE_ME"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # General
    environment: Literal["development", "production", "test"] = "development"
    platform_domain: str = "localhost"
    api_url: str = "http://api.localhost"
    frontend_url: str = "http://app.localhost"
    log_level: str = "INFO"

    # Security
    secret_key: str = Field(default=f"{_SENTINEL}_64_random_chars")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    cors_origins: str = "http://app.localhost,http://localhost:5173"

    # Database
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "rentawhale"
    postgres_user: str = "rentawhale"
    postgres_password: str = f"{_SENTINEL}_db_password"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Provider
    deployment_provider: Literal["docker"] = "docker"
    docker_host_socket: str = "/var/run/docker.sock"
    ingress_network: str = "raw_ingress"
    host_reserved_cpu_cores: float = 1.0
    host_reserved_memory_mb: int = 2048
    host_reserved_disk_gb: int = 10

    # Billing
    billing_tick_seconds: int = 60
    min_balance_hours: float = 1.0

    # Bootstrap admin
    first_admin_email: str = "admin@example.com"
    first_admin_password: str = f"{_SENTINEL}_admin_password"

    # TLS
    acme_email: str = ""
    traefik_tls: bool = False

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def deployment_url_scheme(self) -> str:
        return "https" if self.traefik_tls else "http"

    @field_validator("log_level")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()

    @model_validator(mode="after")
    def _forbid_sentinels_in_production(self) -> "Settings":
        if self.environment == "production":
            offenders = [
                name
                for name in ("secret_key", "postgres_password", "first_admin_password")
                if _SENTINEL in getattr(self, name)
            ]
            if offenders:
                raise ValueError(
                    f"Refusing to start in production with placeholder secrets: {offenders}. "
                    "Set real values in the environment."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
