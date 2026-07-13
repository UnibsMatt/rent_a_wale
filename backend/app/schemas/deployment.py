from __future__ import annotations

import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ApiModel

ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SLUG_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?$")
VOLUME_PATH_RE = re.compile(r"^/(?!\.)[\w\-./]+$")

RestartPolicy = Literal["no", "always", "on-failure", "unless-stopped"]


class ResourceSpec(BaseModel):
    cpu_cores: Decimal = Field(gt=0, le=Decimal("32"))
    memory_mb: int = Field(ge=64, le=262_144)
    storage_gb: int = Field(ge=0, le=1024)  # 0 = stateless, no persistent volume


class VolumeMount(BaseModel):
    """Named volumes only — bind mounts are forbidden by design."""

    name: str = Field(min_length=1, max_length=48, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    container_path: str = Field(min_length=2, max_length=256)

    @field_validator("container_path")
    @classmethod
    def _abs_path(cls, v: str) -> str:
        if not VOLUME_PATH_RE.match(v):
            raise ValueError("container_path must be an absolute path without '..'")
        return v


class ImageSpec(BaseModel):
    image: str = Field(min_length=1, max_length=256)
    command: str | None = Field(default=None, max_length=1024)
    env: dict[str, str] = Field(default_factory=dict)
    web_port: int | None = Field(default=None, ge=1, le=65535)
    volumes: list[VolumeMount] = Field(default_factory=list, max_length=8)
    restart_policy: RestartPolicy = "unless-stopped"

    @field_validator("env")
    @classmethod
    def _env_keys(cls, v: dict[str, str]) -> dict[str, str]:
        if len(v) > 64:
            raise ValueError("Too many environment variables (max 64)")
        for key, value in v.items():
            if not ENV_KEY_RE.match(key):
                raise ValueError(f"Invalid environment variable name: {key!r}")
            if len(value) > 4096:
                raise ValueError(f"Environment value too long for {key!r}")
        return v

    @field_validator("image")
    @classmethod
    def _image_ref(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9]+((\.|_|__|-+|/)[a-z0-9]+)*(:[\w][\w.-]{0,127})?(@sha256:[a-f0-9]{64})?$", v):
            raise ValueError("Invalid image reference")
        return v


class DeploymentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    kind: Literal["image", "compose"]
    resources: ResourceSpec
    hostname: str | None = Field(default=None, description="Preferred subdomain label")
    image_spec: ImageSpec | None = None
    compose_yaml: str | None = Field(default=None, max_length=65_536)
    template_id: uuid.UUID | None = None

    @field_validator("hostname")
    @classmethod
    def _hostname(cls, v: str | None) -> str | None:
        if v is not None and not SLUG_RE.match(v):
            raise ValueError(
                "hostname must be a lowercase DNS label (letters, digits, hyphens, max 40 chars)"
            )
        return v


class EstimateRequest(BaseModel):
    resources: ResourceSpec
    service_count: int = Field(default=1, ge=1, le=10)


class EstimateOut(BaseModel):
    hourly: Decimal
    daily: Decimal
    monthly: Decimal
    plan_name: str
    breakdown: dict[str, str]


class ComposeValidateRequest(BaseModel):
    compose_yaml: str = Field(min_length=1, max_length=65_536)


class ComposeServiceOut(BaseModel):
    name: str
    image: str
    web_port: int | None
    cpu_cores: Decimal
    memory_mb: int
    env_keys: list[str]
    volumes: list[str]
    depends_on: list[str]


class ComposeValidateOut(BaseModel):
    valid: bool
    errors: list[str]
    services: list[ComposeServiceOut]
    aggregate: ResourceSpec | None


class DeploymentServiceOut(ApiModel):
    id: uuid.UUID
    service_name: str
    image: str
    container_name: str | None
    status: str
    restart_count: int
    is_web: bool
    internal_port: int | None


class DeploymentOut(ApiModel):
    id: uuid.UUID
    name: str
    slug: str
    kind: str
    status: str
    cpu_cores: Decimal
    memory_mb: int
    storage_gb: int
    estimated_hourly_cost: Decimal
    public_url: str | None
    failure_reason: str | None
    started_at: datetime | None
    stopped_at: datetime | None
    created_at: datetime
    services: list[DeploymentServiceOut] = []


class DeploymentDetailOut(DeploymentOut):
    spec: dict
    total_credits_spent: Decimal = Decimal("0")


class ServiceStatsOut(BaseModel):
    service_name: str
    cpu_percent: float
    memory_used_mb: float
    memory_limit_mb: float
    network_rx_mb: float
    network_tx_mb: float
    status: str
    restart_count: int
    healthy: bool | None


class DeploymentLogLineOut(ApiModel):
    source: str
    level: str
    message: str
    created_at: datetime


class DeploymentEventOut(ApiModel):
    event_type: str
    payload: dict
    created_at: datetime
