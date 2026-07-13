from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import AuthDep, AuthServiceDep, DbDep
from app.core.rate_limit import read_limiter
from app.repositories.auth import SessionRepository
from app.repositories.deployments import DeploymentRepository
from app.repositories.users import CreditAccountRepository
from app.schemas.auth import SessionOut
from app.schemas.common import Message
from app.schemas.user import ChangePasswordRequest, QuotaOut, UserOut

router = APIRouter(prefix="/users", tags=["users"], dependencies=[read_limiter])


@router.get("/me", response_model=UserOut)
def me(ctx: AuthDep) -> UserOut:
    return UserOut.model_validate(ctx.user)


@router.post("/me/change-password", response_model=Message)
def change_password(
    payload: ChangePasswordRequest, ctx: AuthDep, service: AuthServiceDep
) -> Message:
    service.change_password(
        user=ctx.user, current=payload.current_password, new=payload.new_password, ip=ctx.ip
    )
    return Message(message="Password changed — all sessions were logged out")


@router.get("/me/quota", response_model=QuotaOut)
def quota(ctx: AuthDep, db: DbDep) -> QuotaOut:
    account = CreditAccountRepository(db).get_by_user(ctx.user.id)
    used_cpu, used_mem, used_storage, used_count = DeploymentRepository(
        db
    ).allocated_resources(ctx.user.id)
    return QuotaOut(
        max_cpu_quota=account.max_cpu_quota,
        max_memory_mb_quota=account.max_memory_mb_quota,
        max_storage_gb_quota=account.max_storage_gb_quota,
        max_deployments_quota=account.max_deployments_quota,
        used_cpu=used_cpu,
        used_memory_mb=used_mem,
        used_storage_gb=used_storage,
        used_deployments=used_count,
    )


@router.get("/me/sessions", response_model=list[SessionOut])
def sessions(ctx: AuthDep, db: DbDep) -> list[SessionOut]:
    return [
        SessionOut.model_validate(s)
        for s in SessionRepository(db).list_for_user(ctx.user.id)
    ]
