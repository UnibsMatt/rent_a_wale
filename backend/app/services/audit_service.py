from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import AuditLog
from app.repositories.governance import AuditRepository

audit_log = get_logger("audit")


class AuditService:
    def __init__(self, db: Session) -> None:
        self.repo = AuditRepository(db)

    def record(
        self,
        *,
        actor_id: uuid.UUID | None,
        action: str,
        resource_type: str = "",
        resource_id: str = "",
        ip_address: str = "",
        detail: dict | None = None,
    ) -> None:
        """Persist + emit structured audit line. Joins the caller's transaction."""
        self.repo.add(
            AuditLog(
                actor_id=actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=ip_address,
                detail=detail or {},
            )
        )
        audit_log.info(
            action,
            actor_id=str(actor_id) if actor_id else None,
            resource_type=resource_type,
            resource_id=resource_id,
            ip=ip_address,
        )

    def list_paged(self, *, page: int, page_size: int) -> tuple[list[AuditLog], int]:
        return self.repo.list_paged(page=page, page_size=page_size)
