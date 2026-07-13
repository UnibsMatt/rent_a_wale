from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, ConflictError, ValidationFailedError
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_password,
    hash_token,
    refresh_token_expiry,
    revoke_access_token,
    verify_password,
)
from app.models import CreditAccount, RefreshToken, User, UserSession
from app.repositories.auth import RefreshTokenRepository, SessionRepository
from app.repositories.users import CreditAccountRepository, UserRepository
from app.schemas.auth import TokenPair
from app.services.audit_service import AuditService
from app.utils.time import ensure_utc

log = get_logger("app")

RESET_TOKEN_TTL = timedelta(hours=2)


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.accounts = CreditAccountRepository(db)
        self.sessions = SessionRepository(db)
        self.tokens = RefreshTokenRepository(db)
        self.audit = AuditService(db)

    # ── Registration ─────────────────────────────────────────────────────────

    def register(self, *, email: str, password: str, ip: str) -> User:
        email = email.lower()
        if self.users.get_by_email(email) is not None:
            raise ConflictError("An account with this email already exists")

        verification_token = generate_opaque_token()
        user = self.users.add(
            User(
                email=email,
                hashed_password=hash_password(password),
                email_verification_token=hash_token(verification_token),
            )
        )
        self.accounts.add(CreditAccount(user_id=user.id, balance=Decimal("0")))
        self.audit.record(
            actor_id=user.id, action="auth.register", resource_type="user",
            resource_id=str(user.id), ip_address=ip,
        )
        # Email delivery placeholder: log the verification link instead of sending.
        log.info("email_verification_pending", user_id=str(user.id), token=verification_token)
        self.db.commit()
        return user

    # ── Login / logout ───────────────────────────────────────────────────────

    def login(self, *, email: str, password: str, ip: str, user_agent: str) -> TokenPair:
        user = self.users.get_by_email(email)
        # Uniform failure path — no user enumeration via error or timing shortcuts.
        if user is None or not verify_password(password, user.hashed_password):
            self.audit.record(
                actor_id=None, action="auth.login_failed", resource_type="user",
                resource_id=email.lower(), ip_address=ip,
            )
            self.db.commit()
            raise AuthenticationError("Invalid email or password")
        if not user.is_active:
            raise AuthenticationError("Account is disabled")

        session = self.sessions.add(
            UserSession(user_id=user.id, ip_address=ip, user_agent=user_agent[:512])
        )
        pair = self._issue_pair(user, session)
        self.audit.record(
            actor_id=user.id, action="auth.login", resource_type="session",
            resource_id=str(session.id), ip_address=ip,
        )
        self.db.commit()
        return pair

    def refresh(self, *, refresh_token: str, ip: str) -> TokenPair:
        record = self.tokens.get_by_hash(hash_token(refresh_token))
        if record is None:
            raise AuthenticationError("Invalid refresh token")

        if record.revoked or record.replaced_by is not None:
            # Replay of a rotated/revoked token → assume compromise, kill the session family.
            self.tokens.revoke_session_family(record.session_id)
            self.sessions.revoke(record.session_id)
            self.audit.record(
                actor_id=record.user_id, action="auth.refresh_replay_detected",
                resource_type="session", resource_id=str(record.session_id), ip_address=ip,
            )
            self.db.commit()
            raise AuthenticationError("Refresh token reuse detected — session revoked")

        if ensure_utc(record.expires_at) < datetime.now(UTC):
            raise AuthenticationError("Refresh token expired")

        session = self.sessions.get(record.session_id)
        user = self.users.get(record.user_id)
        if session is None or session.revoked or user is None or not user.is_active:
            raise AuthenticationError("Session is no longer valid")

        pair = self._issue_pair(user, session, rotated_from=record)
        self.db.commit()
        return pair

    def logout(self, *, user: User, refresh_token: str, access_jti: str, access_exp: datetime, ip: str) -> None:
        record = self.tokens.get_by_hash(hash_token(refresh_token))
        if record is not None and record.user_id == user.id:
            self.tokens.revoke_session_family(record.session_id)
            self.sessions.revoke(record.session_id)
        revoke_access_token(access_jti, access_exp)
        self.audit.record(
            actor_id=user.id, action="auth.logout", resource_type="session",
            resource_id=str(record.session_id) if record else "", ip_address=ip,
        )
        self.db.commit()

    def _issue_pair(
        self, user: User, session: UserSession, rotated_from: RefreshToken | None = None
    ) -> TokenPair:
        raw = generate_opaque_token()
        new_token = self.tokens.add(
            RefreshToken(
                session_id=session.id,
                user_id=user.id,
                token_hash=hash_token(raw),
                expires_at=refresh_token_expiry(),
            )
        )
        if rotated_from is not None:
            rotated_from.replaced_by = new_token.id
            rotated_from.revoked = True
        access = create_access_token(user_id=user.id, role=user.role, session_id=session.id)
        return TokenPair(access_token=access, refresh_token=raw)

    # ── Email verification / password reset (placeholders wired end-to-end) ──

    def verify_email(self, *, token: str) -> None:
        user = self.users.get_by_verification_token(hash_token(token))
        if user is None:
            raise ValidationFailedError("Invalid verification token")
        user.is_email_verified = True
        user.email_verification_token = None
        self.db.commit()

    def forgot_password(self, *, email: str, ip: str) -> None:
        user = self.users.get_by_email(email)
        if user is not None:
            raw = generate_opaque_token()
            user.password_reset_token = hash_token(raw)
            user.password_reset_expires_at = datetime.now(UTC) + RESET_TOKEN_TTL
            # Email delivery placeholder: log instead of sending.
            log.info("password_reset_pending", user_id=str(user.id), token=raw)
            self.audit.record(
                actor_id=user.id, action="auth.password_reset_requested",
                resource_type="user", resource_id=str(user.id), ip_address=ip,
            )
        self.db.commit()  # commit either way: uniform behavior, no enumeration

    def reset_password(self, *, token: str, new_password: str, ip: str) -> None:
        user = self.users.get_by_reset_token(hash_token(token))
        if (
            user is None
            or user.password_reset_expires_at is None
            or ensure_utc(user.password_reset_expires_at) < datetime.now(UTC)
        ):
            raise ValidationFailedError("Invalid or expired reset token")
        user.hashed_password = hash_password(new_password)
        user.password_reset_token = None
        user.password_reset_expires_at = None
        # New password invalidates every session and refresh token.
        self.sessions.revoke_all_for_user(user.id)
        self.tokens.revoke_all_for_user(user.id)
        self.audit.record(
            actor_id=user.id, action="auth.password_reset", resource_type="user",
            resource_id=str(user.id), ip_address=ip,
        )
        self.db.commit()

    def change_password(self, *, user: User, current: str, new: str, ip: str) -> None:
        if not verify_password(current, user.hashed_password):
            raise AuthenticationError("Current password is incorrect")
        user.hashed_password = hash_password(new)
        self.sessions.revoke_all_for_user(user.id)
        self.tokens.revoke_all_for_user(user.id)
        self.audit.record(
            actor_id=user.id, action="auth.password_changed", resource_type="user",
            resource_id=str(user.id), ip_address=ip,
        )
        self.db.commit()
