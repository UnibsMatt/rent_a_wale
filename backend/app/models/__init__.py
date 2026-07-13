"""Import every model so Base.metadata is complete for Alembic and create_all."""

from app.models.auth import RefreshToken, UserSession
from app.models.base import Base
from app.models.billing import PricingPlan, UsageRecord
from app.models.credits import CreditAccount, CreditTransaction
from app.models.deployment import (
    Deployment,
    DeploymentEvent,
    DeploymentLog,
    DeploymentService,
)
from app.models.governance import AuditLog, ComposeTemplate, HostMetric, ImageRule
from app.models.user import User

__all__ = [
    "AuditLog",
    "Base",
    "ComposeTemplate",
    "CreditAccount",
    "CreditTransaction",
    "Deployment",
    "DeploymentEvent",
    "DeploymentLog",
    "DeploymentService",
    "HostMetric",
    "ImageRule",
    "PricingPlan",
    "RefreshToken",
    "User",
    "UserSession",
    "UsageRecord",
]
