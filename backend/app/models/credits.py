from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPk, utcnow


class CreditAccount(UUIDPk, Base):
    __tablename__ = "credit_accounts"
    __table_args__ = (CheckConstraint("balance >= 0", name="balance_non_negative"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))

    # Per-user resource quotas (noisy-neighbor protection, adjustable by admins)
    max_cpu_quota: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("4"))
    max_memory_mb_quota: Mapped[int] = mapped_column(Integer, default=8192)
    max_storage_gb_quota: Mapped[int] = mapped_column(Integer, default=50)
    max_deployments_quota: Mapped[int] = mapped_column(Integer, default=10)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user = relationship("User", back_populates="credit_account")


class CreditTransaction(UUIDPk, Base):
    __tablename__ = "credit_transactions"

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("credit_accounts.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(16))  # TransactionKind
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))  # signed: debits negative
    balance_after: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    deployment_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    meta: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
