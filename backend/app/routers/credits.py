from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.core.deps import AuthDep, CreditServiceDep, DbDep
from app.core.exceptions import ValidationFailedError
from app.core.rate_limit import read_limiter
from app.repositories.billing import PricingRepository
from app.schemas.common import Page
from app.schemas.credits import BalanceOut, PricingPlanOut, PurchaseRequest, TransactionOut

router = APIRouter(prefix="/credits", tags=["credits"], dependencies=[read_limiter])


@router.get("/balance", response_model=BalanceOut)
def balance(ctx: AuthDep, service: CreditServiceDep) -> BalanceOut:
    return BalanceOut(**service.balance_summary(ctx.user.id))


@router.post("/purchase", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def purchase(payload: PurchaseRequest, ctx: AuthDep, service: CreditServiceDep) -> TransactionOut:
    tx = service.purchase(
        user_id=ctx.user.id,
        amount=payload.amount,
        idempotency_key=payload.idempotency_key,
        ip=ctx.ip,
    )
    return TransactionOut.model_validate(tx)


@router.get("/transactions", response_model=Page[TransactionOut])
def transactions(
    ctx: AuthDep,
    service: CreditServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[TransactionOut]:
    items, total = service.list_transactions(ctx.user.id, page=page, page_size=page_size)
    return Page(
        items=[TransactionOut.model_validate(t) for t in items],
        total=total, page=page, page_size=page_size,
    )


@router.get("/pricing", response_model=PricingPlanOut)
def active_pricing(ctx: AuthDep, db: DbDep) -> PricingPlanOut:
    plan = PricingRepository(db).active_plan()
    if plan is None:
        raise ValidationFailedError("No active pricing plan configured")
    return PricingPlanOut.model_validate(plan)
