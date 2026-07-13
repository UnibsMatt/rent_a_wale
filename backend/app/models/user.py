from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamped, UUIDPk
from app.models.enums import UserRole


class User(UUIDPk, Timestamped, Base):
    __tablename__ = "users"

    # Friendly sequential number used for container namespacing: user12-nginx
    user_number: Mapped[int] = mapped_column(Integer, Identity(start=1), unique=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16), default=UserRole.USER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Email verification / password reset placeholders (tokens hashed at rest)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verification_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    password_reset_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    credit_account: Mapped["CreditAccount"] = relationship(  # noqa: F821
        back_populates="user", uselist=False, lazy="joined"
    )

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def container_namespace(self) -> str:
        return f"user{self.user_number}"


# Imported at bottom to register the relationship target without a cycle at import time.
from app.models.credits import CreditAccount  # noqa: E402
