from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.models import CreditTransaction
from app.repositories.base import Repository


class CreditTransactionRepository(Repository):
    def add(self, tx: CreditTransaction) -> CreditTransaction:
        self.db.add(tx)
        self.db.flush()
        return tx

    def get_by_idempotency_key(self, key: str) -> CreditTransaction | None:
        return self.db.scalar(
            select(CreditTransaction).where(CreditTransaction.idempotency_key == key)
        )

    def list_for_account(
        self, account_id: uuid.UUID, *, page: int, page_size: int
    ) -> tuple[list[CreditTransaction], int]:
        base = select(CreditTransaction).where(CreditTransaction.account_id == account_id)
        total = self.db.scalar(
            select(func.count()).select_from(base.subquery())
        ) or 0
        rows = self.db.scalars(
            base.order_by(CreditTransaction.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(rows), total
