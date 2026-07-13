"""Cryptographic primitives: password hashing, JWT issuance/verification,
refresh-token generation, and the Redis-backed access-token denylist."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.redis import get_redis

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DENYLIST_PREFIX = "revoked_jti:"


# ── Passwords ────────────────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── Access tokens (JWT) ──────────────────────────────────────────────────────


class TokenPayload:
    def __init__(self, sub: str, role: str, jti: str, session_id: str, exp: datetime) -> None:
        self.sub = sub
        self.role = role
        self.jti = jti
        self.session_id = session_id
        self.exp = exp


def create_access_token(*, user_id: uuid.UUID, role: str, session_id: uuid.UUID) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    claims: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "sid": str(session_id),
        "jti": uuid.uuid4().hex,
        "iat": datetime.now(UTC),
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(claims, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> TokenPayload:
    """Validate signature, expiry, type, and denylist. Raises ValueError on any failure."""
    try:
        claims = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc
    if claims.get("type") != "access":
        raise ValueError("Wrong token type")
    jti = claims.get("jti", "")
    if get_redis().exists(f"{DENYLIST_PREFIX}{jti}"):
        raise ValueError("Token has been revoked")
    return TokenPayload(
        sub=claims["sub"],
        role=claims.get("role", "user"),
        jti=jti,
        session_id=claims.get("sid", ""),
        exp=datetime.fromtimestamp(claims["exp"], tz=UTC),
    )


def revoke_access_token(jti: str, exp: datetime) -> None:
    """Denylist a jti until its natural expiry (no reason to keep it longer)."""
    ttl = max(1, int((exp - datetime.now(UTC)).total_seconds()))
    get_redis().setex(f"{DENYLIST_PREFIX}{jti}", ttl, "1")


# ── Refresh / one-time tokens (opaque, hashed at rest) ───────────────────────


def generate_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def refresh_token_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
