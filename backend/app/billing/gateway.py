"""Payment gateway abstraction. The platform ships with a FakeGateway that approves
every charge (credits are the product being sold; card processing is an integration
concern). Stripe/PayPal implement the same interface later without touching
CreditService."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PaymentResult:
    success: bool
    reference: str
    message: str = ""


class PaymentGateway(ABC):
    @abstractmethod
    def charge(self, *, user_id: uuid.UUID, amount: Decimal, idempotency_key: str) -> PaymentResult: ...


class FakeGateway(PaymentGateway):
    def charge(self, *, user_id: uuid.UUID, amount: Decimal, idempotency_key: str) -> PaymentResult:
        return PaymentResult(success=True, reference=f"fake-{idempotency_key}")


def get_gateway() -> PaymentGateway:
    return FakeGateway()
