from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.billing.gateway import PaymentGateway, get_gateway
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.models import CreditAccount, CreditTransaction
from app.models.enums import DeploymentStatus, TransactionKind
from app.repositories.credits import CreditTransactionRepository
from app.repositories.deployments import DeploymentRepository
from app.repositories.users import CreditAccountRepository
from app.services.audit_service import AuditService


class CreditService:
    def __init__(self, db: Session, gateway: PaymentGateway | None = None) -> None:
        self.db = db
        self.accounts = CreditAccountRepository(db)
        self.transactions = CreditTransactionRepository(db)
        self.deployments = DeploymentRepository(db)
        self.audit = AuditService(db)
        self.gateway = gateway or get_gateway()

    def _account_or_404(self, user_id: uuid.UUID, *, for_update: bool = False) -> CreditAccount:
        account = (
            self.accounts.get_by_user_for_update(user_id)
            if for_update
            else self.accounts.get_by_user(user_id)
        )
        if account is None:
            raise NotFoundError("Credit account not found")
        return account

    def balance_summary(self, user_id: uuid.UUID) -> dict:
        account = self._account_or_404(user_id)
        running = [
            d
            for d in self.deployments.list_for_owner(user_id)
            if d.status == DeploymentStatus.RUNNING
        ]
        hourly = sum((d.estimated_hourly_cost for d in running), Decimal("0"))
        runway = (account.balance / hourly).quantize(Decimal("0.1")) if hourly > 0 else None
        return {
            "balance": account.balance,
            "estimated_hourly_spend": hourly,
            "runway_hours": runway,
        }

    def purchase(
        self, *, user_id: uuid.UUID, amount: Decimal, idempotency_key: str, ip: str
    ) -> CreditTransaction:
        existing = self.transactions.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing  # replay-safe

        payment = self.gateway.charge(
            user_id=user_id, amount=amount, idempotency_key=idempotency_key
        )
        if not payment.success:
            raise ValidationFailedError(f"Payment failed: {payment.message}")

        account = self._account_or_404(user_id, for_update=True)
        account.balance += amount
        tx = self.transactions.add(
            CreditTransaction(
                account_id=account.id,
                kind=TransactionKind.PURCHASE,
                amount=amount,
                balance_after=account.balance,
                idempotency_key=idempotency_key,
                meta={"payment_reference": payment.reference},
            )
        )
        self.audit.record(
            actor_id=user_id, action="credits.purchase", resource_type="transaction",
            resource_id=str(tx.id), ip_address=ip, detail={"amount": str(amount)},
        )
        self.db.commit()
        return tx

    def admin_adjust(
        self, *, admin_id: uuid.UUID, user_id: uuid.UUID, amount: Decimal, reason: str, ip: str
    ) -> CreditTransaction:
        account = self._account_or_404(user_id, for_update=True)
        if account.balance + amount < 0:
            raise ValidationFailedError(
                f"Adjustment would make balance negative (current: {account.balance})"
            )
        account.balance += amount
        tx = self.transactions.add(
            CreditTransaction(
                account_id=account.id,
                kind=TransactionKind.ADJUSTMENT,
                amount=amount,
                balance_after=account.balance,
                meta={"reason": reason, "admin_id": str(admin_id)},
            )
        )
        self.audit.record(
            actor_id=admin_id, action="credits.admin_adjust", resource_type="user",
            resource_id=str(user_id), ip_address=ip,
            detail={"amount": str(amount), "reason": reason},
        )
        self.db.commit()
        return tx

    def list_transactions(
        self, user_id: uuid.UUID, *, page: int, page_size: int
    ) -> tuple[list[CreditTransaction], int]:
        account = self._account_or_404(user_id)
        return self.transactions.list_for_account(account.id, page=page, page_size=page_size)
