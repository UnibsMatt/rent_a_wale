"""FastAPI dependency wiring: DB session, current user (JWT), RBAC guards,
service factories. Routers depend on these — never on concrete constructors."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import TokenPayload, decode_access_token
from app.models import User
from app.repositories.users import UserRepository
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.credit_service import CreditService
from app.services.deployment_service import DeploymentOrchestrationService
from app.services.host_service import HostService

bearer_scheme = HTTPBearer(auto_error=False)

DbDep = Annotated[Session, Depends(get_db)]


@dataclass
class AuthContext:
    user: User
    token: TokenPayload
    ip: str


def get_auth_context(
    request: Request,
    db: DbDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> AuthContext:
    if credentials is None:
        raise AuthenticationError("Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise AuthenticationError(str(exc)) from exc
    user = UserRepository(db).get(uuid.UUID(payload.sub))
    if user is None or not user.is_active:
        raise AuthenticationError("User no longer exists or is disabled")
    ip = request.client.host if request.client else ""
    return AuthContext(user=user, token=payload, ip=ip)


AuthDep = Annotated[AuthContext, Depends(get_auth_context)]


def require_admin(ctx: AuthDep) -> AuthContext:
    if not ctx.user.is_admin:
        raise PermissionDeniedError("Administrator role required")
    return ctx


AdminDep = Annotated[AuthContext, Depends(require_admin)]


# ── Service factories ─────────────────────────────────────────────────────────


def get_auth_service(db: DbDep) -> AuthService:
    return AuthService(db)


def get_credit_service(db: DbDep) -> CreditService:
    return CreditService(db)


def get_deployment_service(db: DbDep) -> DeploymentOrchestrationService:
    return DeploymentOrchestrationService(db)


def get_host_service(db: DbDep) -> HostService:
    return HostService(db)


def get_audit_service(db: DbDep) -> AuditService:
    return AuditService(db)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
CreditServiceDep = Annotated[CreditService, Depends(get_credit_service)]
DeploymentServiceDep = Annotated[DeploymentOrchestrationService, Depends(get_deployment_service)]
HostServiceDep = Annotated[HostService, Depends(get_host_service)]
AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]
