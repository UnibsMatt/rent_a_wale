"""Image allow/block rules, compose templates, audit logs, host metrics."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPk, utcnow
from app.models.enums import TemplateStatus


class ImageRule(UUIDPk, Base):
    """Allowlist/blocklist entry. Patterns: exact `repo:tag`, `repo` (any tag), or
    `namespace/*` prefix wildcard. Block rules always win over allow rules."""

    __tablename__ = "images"

    pattern: Mapped[str] = mapped_column(String(256), unique=True)
    mode: Mapped[str] = mapped_column(String(8))  # ImageRuleMode
    reason: Mapped[str] = mapped_column(String(256), default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ComposeTemplate(UUIDPk, Base):
    __tablename__ = "compose_templates"

    submitted_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    compose_yaml: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=TemplateStatus.PENDING, index=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(UUIDPk, Base):
    __tablename__ = "audit_logs"

    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)  # e.g. "auth.login"
    resource_type: Mapped[str] = mapped_column(String(32), default="")
    resource_id: Mapped[str] = mapped_column(String(64), default="")
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class HostMetric(UUIDPk, Base):
    __tablename__ = "host_metrics"

    cpu_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    memory_used_mb: Mapped[int] = mapped_column(Integer, default=0)
    memory_total_mb: Mapped[int] = mapped_column(Integer, default=0)
    disk_used_gb: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    disk_total_gb: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    running_containers: Mapped[int] = mapped_column(Integer, default=0)
    sampled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
