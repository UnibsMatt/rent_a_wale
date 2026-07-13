from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import func, select

from app.models import (
    Deployment,
    DeploymentEvent,
    DeploymentLog,
    DeploymentService,
    UsageRecord,
)
from app.models.enums import DeploymentStatus
from app.repositories.base import Repository

# Statuses that count against quotas and host capacity.
ACTIVE_STATUSES = (
    DeploymentStatus.PENDING,
    DeploymentStatus.PROVISIONING,
    DeploymentStatus.RUNNING,
    DeploymentStatus.STOPPING,
)


class DeploymentRepository(Repository):
    def add(self, deployment: Deployment) -> Deployment:
        self.db.add(deployment)
        self.db.flush()
        return deployment

    def get(self, deployment_id: uuid.UUID) -> Deployment | None:
        return self.db.get(Deployment, deployment_id)

    def get_for_update(self, deployment_id: uuid.UUID) -> Deployment | None:
        return self.db.scalar(
            select(Deployment).where(Deployment.id == deployment_id).with_for_update()
        )

    def slug_exists(self, slug: str) -> bool:
        return self.db.scalar(select(Deployment.id).where(Deployment.slug == slug)) is not None

    def list_for_owner(
        self, owner_id: uuid.UUID, *, include_deleted: bool = False
    ) -> list[Deployment]:
        q = select(Deployment).where(Deployment.owner_id == owner_id)
        if not include_deleted:
            q = q.where(Deployment.deleted_at.is_(None))
        return list(self.db.scalars(q.order_by(Deployment.created_at.desc())).all())

    def list_all(self, *, page: int, page_size: int) -> tuple[list[Deployment], int]:
        base = select(Deployment).where(Deployment.deleted_at.is_(None))
        total = self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = self.db.scalars(
            base.order_by(Deployment.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(rows), total

    def list_by_status(self, status: DeploymentStatus) -> list[Deployment]:
        return list(
            self.db.scalars(select(Deployment).where(Deployment.status == status)).all()
        )

    def list_active(self) -> list[Deployment]:
        return list(
            self.db.scalars(
                select(Deployment).where(Deployment.status.in_(ACTIVE_STATUSES))
            ).all()
        )

    def allocated_resources(
        self, owner_id: uuid.UUID | None = None
    ) -> tuple[Decimal, int, int, int]:
        """(cpu, memory_mb, storage_gb, count) allocated by active deployments."""
        q = select(
            func.coalesce(func.sum(Deployment.cpu_cores), 0),
            func.coalesce(func.sum(Deployment.memory_mb), 0),
            func.coalesce(func.sum(Deployment.storage_gb), 0),
            func.count(Deployment.id),
        ).where(Deployment.status.in_(ACTIVE_STATUSES))
        if owner_id is not None:
            q = q.where(Deployment.owner_id == owner_id)
        cpu, mem, storage, count = self.db.execute(q).one()
        return Decimal(cpu), int(mem), int(storage), int(count)

    # ── Services ────────────────────────────────────────────────────────────

    def add_service(self, service: DeploymentService) -> DeploymentService:
        self.db.add(service)
        self.db.flush()
        return service

    def services_for(self, deployment_id: uuid.UUID) -> list[DeploymentService]:
        return list(
            self.db.scalars(
                select(DeploymentService)
                .where(DeploymentService.deployment_id == deployment_id)
                .order_by(DeploymentService.service_name)
            ).all()
        )

    # ── Events (outbox) ─────────────────────────────────────────────────────

    def add_event(self, event: DeploymentEvent) -> DeploymentEvent:
        self.db.add(event)
        self.db.flush()
        return event

    def get_event(self, event_id: uuid.UUID) -> DeploymentEvent | None:
        return self.db.get(DeploymentEvent, event_id)

    def undispatched_events(self, limit: int = 100) -> list[DeploymentEvent]:
        return list(
            self.db.scalars(
                select(DeploymentEvent)
                .where(DeploymentEvent.dispatched.is_(False))
                .order_by(DeploymentEvent.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            ).all()
        )

    def events_for(self, deployment_id: uuid.UUID, limit: int = 100) -> list[DeploymentEvent]:
        return list(
            self.db.scalars(
                select(DeploymentEvent)
                .where(DeploymentEvent.deployment_id == deployment_id)
                .order_by(DeploymentEvent.created_at.desc())
                .limit(limit)
            ).all()
        )

    # ── Logs ────────────────────────────────────────────────────────────────

    def add_log(self, log: DeploymentLog) -> DeploymentLog:
        self.db.add(log)
        return log

    def logs_for(self, deployment_id: uuid.UUID, limit: int = 500) -> list[DeploymentLog]:
        return list(
            self.db.scalars(
                select(DeploymentLog)
                .where(DeploymentLog.deployment_id == deployment_id)
                .order_by(DeploymentLog.created_at.desc())
                .limit(limit)
            ).all()
        )

    # ── Usage ───────────────────────────────────────────────────────────────

    def total_credits_spent(self, deployment_id: uuid.UUID) -> Decimal:
        return Decimal(
            self.db.scalar(
                select(func.coalesce(func.sum(UsageRecord.credits_charged), 0)).where(
                    UsageRecord.deployment_id == deployment_id
                )
            )
            or 0
        )
