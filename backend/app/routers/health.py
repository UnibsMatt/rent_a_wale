from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.core.db import SessionLocal
from app.core.redis import get_redis

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness + dependency readiness (used by compose healthchecks)."""
    checks = {"database": False, "redis": False}
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass
    try:
        checks["redis"] = bool(get_redis().ping())
    except Exception:
        pass
    return {"status": "ok" if all(checks.values()) else "degraded", "checks": checks}
