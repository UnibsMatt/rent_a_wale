from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ApiModel


class UserOut(ApiModel):
    id: uuid.UUID
    user_number: int
    email: str
    role: str
    is_active: bool
    is_email_verified: bool
    created_at: datetime


class UserWithBalance(UserOut):
    balance: Decimal


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class QuotaOut(BaseModel):
    max_cpu_quota: Decimal
    max_memory_mb_quota: int
    max_storage_gb_quota: int
    max_deployments_quota: int
    used_cpu: Decimal
    used_memory_mb: int
    used_storage_gb: int
    used_deployments: int
