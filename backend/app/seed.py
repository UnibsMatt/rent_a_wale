"""Idempotent bootstrap: default pricing plan, image allowlist, first admin.

Run after migrations: `python -m app.seed` (the container entrypoint does this).
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.models import CreditAccount, ImageRule, PricingPlan, User
from app.models.enums import ImageRuleMode, UserRole

log = get_logger("app")

# With these prices: 1 CPU + 2 GB RAM = 3 credits/hour; 2 CPU + 4 GB = 6 credits/hour.
DEFAULT_PLAN = dict(
    name="default",
    is_active=True,
    base_cost_per_hour=Decimal("0"),
    cpu_cost_per_core_hour=Decimal("1"),
    memory_cost_per_gb_hour=Decimal("1"),
    storage_cost_per_gb_hour=Decimal("0.05"),
    service_cost_per_hour=Decimal("0.25"),
)

DEFAULT_ALLOWED_IMAGES = [
    "nginx", "httpd", "caddy", "traefik/whoami",
    "redis", "valkey/valkey", "memcached",
    "postgres", "mysql", "mariadb", "mongo",
    "node", "python", "php", "golang",
    "wordpress", "ghost", "nextcloud", "grafana/grafana",
    "adminer", "phpmyadmin", "portainer/portainer-ce",
    "busybox", "alpine", "hello-world",
    "minio/minio", "rabbitmq", "elasticsearch", "bitnami/*",
]


def seed(db: Session) -> None:
    if db.scalar(select(PricingPlan).where(PricingPlan.name == DEFAULT_PLAN["name"])) is None:
        db.add(PricingPlan(**DEFAULT_PLAN))
        log.info("seeded_pricing_plan", name=DEFAULT_PLAN["name"])

    for pattern in DEFAULT_ALLOWED_IMAGES:
        if db.scalar(select(ImageRule).where(ImageRule.pattern == pattern)) is None:
            db.add(ImageRule(pattern=pattern, mode=ImageRuleMode.ALLOW, reason="default allowlist"))

    admin_exists = db.scalar(select(User).where(User.role == UserRole.ADMIN)) is not None
    if not admin_exists:
        admin = User(
            email=settings.first_admin_email.lower(),
            hashed_password=hash_password(settings.first_admin_password),
            role=UserRole.ADMIN,
            is_active=True,
            is_email_verified=True,
        )
        db.add(admin)
        db.flush()
        db.add(CreditAccount(user_id=admin.id, balance=Decimal("0")))
        log.info("seeded_admin", email=settings.first_admin_email)

    db.commit()


def main() -> None:
    configure_logging()
    with SessionLocal() as db:
        seed(db)
    log.info("seed_complete")


if __name__ == "__main__":
    main()
