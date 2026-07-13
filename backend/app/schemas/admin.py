from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ApiModel


class AdjustCreditsRequest(BaseModel):
    amount: Decimal = Field(description="Signed credit adjustment")
    reason: str = Field(min_length=3, max_length=256)


class AdjustQuotaRequest(BaseModel):
    max_cpu_quota: Decimal | None = Field(default=None, gt=0)
    max_memory_mb_quota: int | None = Field(default=None, gt=0)
    max_storage_gb_quota: int | None = Field(default=None, gt=0)
    max_deployments_quota: int | None = Field(default=None, gt=0)


class ImageRuleCreate(BaseModel):
    pattern: str = Field(min_length=1, max_length=256)
    mode: str = Field(pattern="^(allow|block)$")
    reason: str = Field(default="", max_length=256)


class ImageRuleOut(ApiModel):
    id: uuid.UUID
    pattern: str
    mode: str
    reason: str
    created_at: datetime


class AuditLogOut(ApiModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: str
    ip_address: str
    detail: dict
    created_at: datetime


class HostUsageOut(BaseModel):
    cpu_percent: float
    memory_used_mb: int
    memory_total_mb: int
    disk_used_gb: float
    disk_total_gb: float
    running_containers: int
    allocated_cpu: Decimal
    allocated_memory_mb: int
    allocated_storage_gb: int
    allocatable_cpu: Decimal
    allocatable_memory_mb: int
    allocatable_storage_gb: int
    sampled_at: datetime | None


class TemplateOut(ApiModel):
    id: uuid.UUID
    name: str
    description: str
    compose_yaml: str
    status: str
    submitted_by: uuid.UUID
    created_at: datetime


class TemplateCreate(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    description: str = Field(default="", max_length=2048)
    compose_yaml: str = Field(min_length=1, max_length=65_536)


class TemplateReview(BaseModel):
    approve: bool
