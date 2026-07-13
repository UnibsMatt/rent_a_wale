from __future__ import annotations

from fastapi import APIRouter, Request, status

from app.core.deps import AuthDep, AuthServiceDep
from app.core.rate_limit import auth_limiter
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenPair,
    VerifyEmailRequest,
)
from app.schemas.common import Message
from app.schemas.user import UserOut

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[auth_limiter])


def _ip(request: Request) -> str:
    return request.client.host if request.client else ""


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, service: AuthServiceDep) -> UserOut:
    user = service.register(email=payload.email, password=payload.password, ip=_ip(request))
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, request: Request, service: AuthServiceDep) -> TokenPair:
    return service.login(
        email=payload.email,
        password=payload.password,
        ip=_ip(request),
        user_agent=request.headers.get("user-agent", ""),
    )


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, request: Request, service: AuthServiceDep) -> TokenPair:
    return service.refresh(refresh_token=payload.refresh_token, ip=_ip(request))


@router.post("/logout", response_model=Message)
def logout(payload: LogoutRequest, ctx: AuthDep, service: AuthServiceDep) -> Message:
    service.logout(
        user=ctx.user,
        refresh_token=payload.refresh_token,
        access_jti=ctx.token.jti,
        access_exp=ctx.token.exp,
        ip=ctx.ip,
    )
    return Message(message="Logged out")


@router.post("/verify-email", response_model=Message)
def verify_email(payload: VerifyEmailRequest, service: AuthServiceDep) -> Message:
    service.verify_email(token=payload.token)
    return Message(message="Email verified")


@router.post("/forgot-password", response_model=Message)
def forgot_password(
    payload: ForgotPasswordRequest, request: Request, service: AuthServiceDep
) -> Message:
    service.forgot_password(email=payload.email, ip=_ip(request))
    return Message(message="If the account exists, a reset link has been sent")


@router.post("/reset-password", response_model=Message)
def reset_password(
    payload: ResetPasswordRequest, request: Request, service: AuthServiceDep
) -> Message:
    service.reset_password(
        token=payload.token, new_password=payload.new_password, ip=_ip(request)
    )
    return Message(message="Password has been reset — please log in again")
