from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"


class DeploymentKind(StrEnum):
    IMAGE = "image"
    COMPOSE = "compose"


class DeploymentStatus(StrEnum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    DELETING = "deleting"
    DELETED = "deleted"
    CREDIT_EXHAUSTED = "credit_exhausted"

    @property
    def is_billable(self) -> bool:
        return self == DeploymentStatus.RUNNING

    @property
    def is_terminal(self) -> bool:
        return self in (DeploymentStatus.DELETED, DeploymentStatus.FAILED)


class DeploymentEventType(StrEnum):
    CREATED = "created"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    DELETED = "deleted"
    CREDIT_EXHAUSTED = "credit_exhausted"


class TransactionKind(StrEnum):
    PURCHASE = "purchase"
    USAGE = "usage"
    ADJUSTMENT = "adjustment"
    REFUND = "refund"


class ImageRuleMode(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"


class TemplateStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class LogSource(StrEnum):
    SYSTEM = "system"
    BILLING = "billing"
    PROVIDER = "provider"
