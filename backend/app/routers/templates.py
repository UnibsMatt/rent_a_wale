from __future__ import annotations

from fastapi import APIRouter, status

from app.core.deps import AuthDep, AuditServiceDep, DbDep, DeploymentServiceDep
from app.core.exceptions import ValidationFailedError
from app.core.rate_limit import read_limiter
from app.models import ComposeTemplate
from app.repositories.governance import TemplateRepository
from app.schemas.admin import TemplateCreate, TemplateOut

router = APIRouter(prefix="/templates", tags=["templates"], dependencies=[read_limiter])


@router.get("", response_model=list[TemplateOut])
def list_approved(ctx: AuthDep, db: DbDep) -> list[TemplateOut]:
    return [TemplateOut.model_validate(t) for t in TemplateRepository(db).list_approved()]


@router.post("", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
def submit(
    payload: TemplateCreate,
    ctx: AuthDep,
    db: DbDep,
    deployments: DeploymentServiceDep,
    audit: AuditServiceDep,
) -> TemplateOut:
    validation = deployments.validate_compose(payload.compose_yaml)
    if not validation["valid"]:
        raise ValidationFailedError(
            "Template compose file is invalid", detail={"errors": validation["errors"]}
        )
    template = TemplateRepository(db).add(
        ComposeTemplate(
            submitted_by=ctx.user.id,
            name=payload.name,
            description=payload.description,
            compose_yaml=payload.compose_yaml,
        )
    )
    audit.record(
        actor_id=ctx.user.id, action="template.submit", resource_type="template",
        resource_id=str(template.id), ip_address=ctx.ip,
    )
    db.commit()
    return TemplateOut.model_validate(template)
