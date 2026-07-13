from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPk, utcnow


class PricingPlan(UUIDPk, Base):
    """Configurable pricing. Exactly one plan is active at a time; changing prices
    means activating a new plan — running deployments keep their frozen snapshot."""

    __tablename__ = "pricing_plans"

    name: Mapped[str] = mapped_column(String(64), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    base_cost_per_hour: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0.5"))
    cpu_cost_per_core_hour: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("1"))
    memory_cost_per_gb_hour: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("1"))
    storage_cost_per_gb_hour: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0.05")
    )
    service_cost_per_hour: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0.25")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def snapshot(self) -> dict:
        return {
            "plan_id": str(self.id),
            "plan_name": self.name,
            "base_cost_per_hour": str(self.base_cost_per_hour),
            "cpu_cost_per_core_hour": str(self.cpu_cost_per_core_hour),
            "memory_cost_per_gb_hour": str(self.memory_cost_per_gb_hour),
            "storage_cost_per_gb_hour": str(self.storage_cost_per_gb_hour),
            "service_cost_per_hour": str(self.service_cost_per_hour),
        }


class UsageRecord(UUIDPk, Base):
    """One billed period per deployment per tick. The (deployment_id, period_start)
    uniqueness makes the billing tick idempotent."""

    __tablename__ = "usage_records"
    __table_args__ = (
        UniqueConstraint("deployment_id", "period_start", name="uq_usage_period"),
    )

    deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deployments.id", ondelete="CASCADE"), index=True
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    credits_charged: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    price_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
