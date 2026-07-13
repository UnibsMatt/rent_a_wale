from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update

from app.models import PricingPlan, UsageRecord
from app.repositories.base import Repository


class PricingRepository(Repository):
    def active_plan(self) -> PricingPlan | None:
        return self.db.scalar(select(PricingPlan).where(PricingPlan.is_active.is_(True)))

    def list_all(self) -> list[PricingPlan]:
        return list(
            self.db.scalars(select(PricingPlan).order_by(PricingPlan.created_at.desc())).all()
        )

    def add(self, plan: PricingPlan) -> PricingPlan:
        self.db.add(plan)
        self.db.flush()
        return plan

    def deactivate_all(self) -> None:
        self.db.execute(update(PricingPlan).values(is_active=False))

    def activate(self, plan_id: uuid.UUID) -> None:
        self.deactivate_all()
        self.db.execute(
            update(PricingPlan).where(PricingPlan.id == plan_id).values(is_active=True)
        )


class UsageRepository(Repository):
    def add(self, record: UsageRecord) -> UsageRecord:
        self.db.add(record)
        self.db.flush()
        return record

    def period_exists(self, deployment_id: uuid.UUID, period_start: datetime) -> bool:
        return (
            self.db.scalar(
                select(UsageRecord.id).where(
                    UsageRecord.deployment_id == deployment_id,
                    UsageRecord.period_start == period_start,
                )
            )
            is not None
        )
