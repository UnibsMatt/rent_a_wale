from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ApiModel


class BalanceOut(BaseModel):
    balance: Decimal
    estimated_hourly_spend: Decimal
    runway_hours: Decimal | None  # None when nothing is running


class PurchaseRequest(BaseModel):
    amount: Decimal = Field(gt=0, le=Decimal("1000000"))
    idempotency_key: str = Field(min_length=8, max_length=128)


class TransactionOut(ApiModel):
    id: uuid.UUID
    kind: str
    amount: Decimal
    balance_after: Decimal
    deployment_id: uuid.UUID | None
    created_at: datetime


class PricingPlanOut(ApiModel):
    id: uuid.UUID
    name: str
    is_active: bool
    base_cost_per_hour: Decimal
    cpu_cost_per_core_hour: Decimal
    memory_cost_per_gb_hour: Decimal
    storage_cost_per_gb_hour: Decimal
    service_cost_per_hour: Decimal
    created_at: datetime


class PricingPlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    base_cost_per_hour: Decimal = Field(ge=0)
    cpu_cost_per_core_hour: Decimal = Field(ge=0)
    memory_cost_per_gb_hour: Decimal = Field(ge=0)
    storage_cost_per_gb_hour: Decimal = Field(ge=0)
    service_cost_per_hour: Decimal = Field(ge=0)
    activate: bool = True
