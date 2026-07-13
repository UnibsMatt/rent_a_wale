from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamped, UUIDPk, utcnow
from app.models.enums import DeploymentStatus


class Deployment(UUIDPk, Timestamped, Base):
    __tablename__ = "deployments"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(64))
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # subdomain label
    kind: Mapped[str] = mapped_column(String(16))  # DeploymentKind
    status: Mapped[str] = mapped_column(
        String(32), default=DeploymentStatus.PENDING, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), default="docker")
    node_id: Mapped[str] = mapped_column(String(64), default="local")  # future multi-VM

    # Aggregate requested resources (sum over services for compose)
    cpu_cores: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    memory_mb: Mapped[int] = mapped_column(Integer)
    storage_gb: Mapped[int] = mapped_column(Integer)

    # Full validated spec (image config or interpreted compose), never raw user input.
    spec: Mapped[dict] = mapped_column(JSONB)
    # Pricing frozen at creation time; billing never re-prices a running workload.
    price_snapshot: Mapped[dict] = mapped_column(JSONB)
    estimated_hourly_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4))

    public_url: Mapped[str | None] = mapped_column(String(256), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("compose_templates.id", ondelete="SET NULL"), nullable=True
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    services: Mapped[list["DeploymentService"]] = relationship(
        back_populates="deployment", cascade="all, delete-orphan", lazy="selectin"
    )


class DeploymentService(UUIDPk, Base):
    """One container of a deployment (a single row for image deployments)."""

    __tablename__ = "deployment_services"

    deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deployments.id", ondelete="CASCADE"), index=True
    )
    service_name: Mapped[str] = mapped_column(String(64))
    image: Mapped[str] = mapped_column(String(256))
    container_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    container_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    restart_count: Mapped[int] = mapped_column(Integer, default=0)
    is_web: Mapped[bool] = mapped_column(Boolean, default=False)
    internal_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    deployment = relationship("Deployment", back_populates="services")


class DeploymentEvent(UUIDPk, Base):
    """Transactional outbox for lifecycle events."""

    __tablename__ = "deployment_events"

    deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deployments.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(32), index=True)  # DeploymentEventType
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    dispatched: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class DeploymentLog(UUIDPk, Base):
    """Platform-side deployment log lines (system/billing). Container stdout/stderr
    is streamed from the engine, not stored here."""

    __tablename__ = "deployment_logs"

    deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deployments.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(16))  # LogSource
    level: Mapped[str] = mapped_column(String(16), default="info")
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
