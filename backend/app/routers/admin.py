from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Query, status

from app.core.deps import (
    AdminDep,
    AuditServiceDep,
    CreditServiceDep,
    DbDep,
    DeploymentServiceDep,
    HostServiceDep,
)
from app.core.exceptions import NotFoundError
from app.core.rate_limit import read_limiter
from app.models import ImageRule, PricingPlan
from app.models.enums import TemplateStatus
from app.repositories.billing import PricingRepository
from app.repositories.governance import ImageRuleRepository, TemplateRepository
from app.repositories.users import CreditAccountRepository, UserRepository
from app.schemas.admin import (
    AdjustCreditsRequest,
    AdjustQuotaRequest,
    AuditLogOut,
    HostUsageOut,
    ImageRuleCreate,
    ImageRuleOut,
    TemplateOut,
    TemplateReview,
)
from app.schemas.common import Message, Page
from app.schemas.credits import PricingPlanCreate, PricingPlanOut, TransactionOut
from app.schemas.deployment import DeploymentOut
from app.schemas.user import UserWithBalance

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[read_limiter])


# ── Users ─────────────────────────────────────────────────────────────────────


@router.get("/users", response_model=Page[UserWithBalance])
def list_users(
    ctx: AdminDep, db: DbDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[UserWithBalance]:
    users, total = UserRepository(db).list_paged(page=page, page_size=page_size)
    accounts = CreditAccountRepository(db)
    items = []
    for user in users:
        account = accounts.get_by_user(user.id)
        items.append(
            UserWithBalance(
                **{f: getattr(user, f) for f in (
                    "id", "user_number", "email", "role",
                    "is_active", "is_email_verified", "created_at",
                )},
                balance=account.balance if account else Decimal("0"),
            )
        )
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.post("/users/{user_id}/credits", response_model=TransactionOut)
def adjust_credits(
    user_id: uuid.UUID, payload: AdjustCreditsRequest, ctx: AdminDep, credits: CreditServiceDep
) -> TransactionOut:
    tx = credits.admin_adjust(
        admin_id=ctx.user.id, user_id=user_id,
        amount=payload.amount, reason=payload.reason, ip=ctx.ip,
    )
    return TransactionOut.model_validate(tx)


@router.patch("/users/{user_id}/quotas", response_model=Message)
def adjust_quotas(
    user_id: uuid.UUID, payload: AdjustQuotaRequest,
    ctx: AdminDep, db: DbDep, audit: AuditServiceDep,
) -> Message:
    account = CreditAccountRepository(db).get_by_user(user_id)
    if account is None:
        raise NotFoundError("User has no credit account")
    for field in (
        "max_cpu_quota", "max_memory_mb_quota", "max_storage_gb_quota", "max_deployments_quota",
    ):
        value = getattr(payload, field)
        if value is not None:
            setattr(account, field, value)
    audit.record(
        actor_id=ctx.user.id, action="admin.adjust_quotas", resource_type="user",
        resource_id=str(user_id), ip_address=ctx.ip,
        detail=payload.model_dump(exclude_none=True, mode="json"),
    )
    db.commit()
    return Message(message="Quotas updated")


@router.post("/users/{user_id}/deactivate", response_model=Message)
def deactivate_user(
    user_id: uuid.UUID, ctx: AdminDep, db: DbDep, audit: AuditServiceDep
) -> Message:
    user = UserRepository(db).get(user_id)
    if user is None:
        raise NotFoundError("User not found")
    user.is_active = False
    audit.record(
        actor_id=ctx.user.id, action="admin.deactivate_user", resource_type="user",
        resource_id=str(user_id), ip_address=ctx.ip,
    )
    db.commit()
    return Message(message="User deactivated")


# ── Deployments ───────────────────────────────────────────────────────────────


@router.get("/deployments", response_model=Page[DeploymentOut])
def list_deployments(
    ctx: AdminDep, db: DbDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[DeploymentOut]:
    from app.repositories.deployments import DeploymentRepository

    items, total = DeploymentRepository(db).list_all(page=page, page_size=page_size)
    return Page(
        items=[DeploymentOut.model_validate(d) for d in items],
        total=total, page=page, page_size=page_size,
    )


@router.post(
    "/deployments/{deployment_id}/stop",
    response_model=DeploymentOut, status_code=status.HTTP_202_ACCEPTED,
)
def stop_any(
    deployment_id: uuid.UUID, ctx: AdminDep, service: DeploymentServiceDep
) -> DeploymentOut:
    # Admin context passes ownership checks via role.
    return DeploymentOut.model_validate(
        service.stop(user=ctx.user, deployment_id=deployment_id, ip=ctx.ip)
    )


@router.delete(
    "/deployments/{deployment_id}",
    response_model=DeploymentOut, status_code=status.HTTP_202_ACCEPTED,
)
def delete_any(
    deployment_id: uuid.UUID, ctx: AdminDep, service: DeploymentServiceDep
) -> DeploymentOut:
    return DeploymentOut.model_validate(
        service.delete(user=ctx.user, deployment_id=deployment_id, ip=ctx.ip)
    )


# ── Pricing ───────────────────────────────────────────────────────────────────


@router.get("/pricing", response_model=list[PricingPlanOut])
def list_pricing(ctx: AdminDep, db: DbDep) -> list[PricingPlanOut]:
    return [PricingPlanOut.model_validate(p) for p in PricingRepository(db).list_all()]


@router.post("/pricing", response_model=PricingPlanOut, status_code=status.HTTP_201_CREATED)
def create_pricing(
    payload: PricingPlanCreate, ctx: AdminDep, db: DbDep, audit: AuditServiceDep
) -> PricingPlanOut:
    repo = PricingRepository(db)
    plan = repo.add(PricingPlan(
        name=payload.name,
        base_cost_per_hour=payload.base_cost_per_hour,
        cpu_cost_per_core_hour=payload.cpu_cost_per_core_hour,
        memory_cost_per_gb_hour=payload.memory_cost_per_gb_hour,
        storage_cost_per_gb_hour=payload.storage_cost_per_gb_hour,
        service_cost_per_hour=payload.service_cost_per_hour,
    ))
    if payload.activate:
        repo.activate(plan.id)
        plan.is_active = True
    audit.record(
        actor_id=ctx.user.id, action="admin.pricing_created", resource_type="pricing_plan",
        resource_id=str(plan.id), ip_address=ctx.ip,
    )
    db.commit()
    return PricingPlanOut.model_validate(plan)


@router.post("/pricing/{plan_id}/activate", response_model=Message)
def activate_pricing(
    plan_id: uuid.UUID, ctx: AdminDep, db: DbDep, audit: AuditServiceDep
) -> Message:
    repo = PricingRepository(db)
    repo.activate(plan_id)
    audit.record(
        actor_id=ctx.user.id, action="admin.pricing_activated", resource_type="pricing_plan",
        resource_id=str(plan_id), ip_address=ctx.ip,
    )
    db.commit()
    return Message(message="Pricing plan activated — applies to new deployments only")


# ── Image rules ───────────────────────────────────────────────────────────────


@router.get("/images", response_model=list[ImageRuleOut])
def list_image_rules(ctx: AdminDep, db: DbDep) -> list[ImageRuleOut]:
    return [ImageRuleOut.model_validate(r) for r in ImageRuleRepository(db).list_all()]


@router.post("/images", response_model=ImageRuleOut, status_code=status.HTTP_201_CREATED)
def create_image_rule(
    payload: ImageRuleCreate, ctx: AdminDep, db: DbDep, audit: AuditServiceDep
) -> ImageRuleOut:
    rule = ImageRuleRepository(db).add(ImageRule(
        pattern=payload.pattern, mode=payload.mode,
        reason=payload.reason, created_by=ctx.user.id,
    ))
    audit.record(
        actor_id=ctx.user.id, action=f"admin.image_{payload.mode}", resource_type="image_rule",
        resource_id=payload.pattern, ip_address=ctx.ip,
    )
    db.commit()
    return ImageRuleOut.model_validate(rule)


@router.delete("/images/{rule_id}", response_model=Message)
def delete_image_rule(
    rule_id: uuid.UUID, ctx: AdminDep, db: DbDep, audit: AuditServiceDep
) -> Message:
    repo = ImageRuleRepository(db)
    rule = repo.get(rule_id)
    if rule is None:
        raise NotFoundError("Rule not found")
    repo.delete(rule)
    audit.record(
        actor_id=ctx.user.id, action="admin.image_rule_deleted", resource_type="image_rule",
        resource_id=rule.pattern, ip_address=ctx.ip,
    )
    db.commit()
    return Message(message="Rule deleted")


# ── Templates ─────────────────────────────────────────────────────────────────


@router.get("/templates", response_model=list[TemplateOut])
def list_templates(ctx: AdminDep, db: DbDep) -> list[TemplateOut]:
    return [TemplateOut.model_validate(t) for t in TemplateRepository(db).list_all()]


@router.post("/templates/{template_id}/review", response_model=TemplateOut)
def review_template(
    template_id: uuid.UUID, payload: TemplateReview,
    ctx: AdminDep, db: DbDep, audit: AuditServiceDep,
) -> TemplateOut:
    template = TemplateRepository(db).get(template_id)
    if template is None:
        raise NotFoundError("Template not found")
    template.status = TemplateStatus.APPROVED if payload.approve else TemplateStatus.REJECTED
    template.reviewed_by = ctx.user.id
    audit.record(
        actor_id=ctx.user.id, action="admin.template_reviewed", resource_type="template",
        resource_id=str(template_id), ip_address=ctx.ip,
        detail={"approved": payload.approve},
    )
    db.commit()
    return TemplateOut.model_validate(template)


# ── Host / audit ──────────────────────────────────────────────────────────────


@router.get("/host", response_model=HostUsageOut)
def host_usage(ctx: AdminDep, host: HostServiceDep) -> HostUsageOut:
    return HostUsageOut(**host.usage_overview())


@router.get("/audit-logs", response_model=Page[AuditLogOut])
def audit_logs(
    ctx: AdminDep, audit: AuditServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> Page[AuditLogOut]:
    items, total = audit.list_paged(page=page, page_size=page_size)
    return Page(
        items=[AuditLogOut.model_validate(a) for a in items],
        total=total, page=page, page_size=page_size,
    )
