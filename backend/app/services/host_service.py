"""Host capacity accounting: provider totals − platform reservation − DB allocations."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import HostCapacityError
from app.providers import get_provider
from app.providers.base import DeploymentProvider
from app.repositories.deployments import DeploymentRepository
from app.repositories.governance import MetricsRepository


@dataclass
class Allocatable:
    cpu: Decimal
    memory_mb: int
    storage_gb: int


class HostService:
    def __init__(self, db: Session, provider: DeploymentProvider | None = None) -> None:
        self.db = db
        self.deployments = DeploymentRepository(db)
        self.metrics = MetricsRepository(db)
        self.provider = provider or get_provider()

    def allocatable(self) -> Allocatable:
        capacity = self.provider.host_capacity()
        allocated_cpu, allocated_mem, allocated_storage, _ = (
            self.deployments.allocated_resources()
        )
        free_disk_gb = int(capacity.total_disk_gb - capacity.used_disk_gb)
        return Allocatable(
            cpu=capacity.total_cpu_cores
            - Decimal(str(settings.host_reserved_cpu_cores))
            - allocated_cpu,
            memory_mb=capacity.total_memory_mb
            - settings.host_reserved_memory_mb
            - allocated_mem,
            storage_gb=free_disk_gb - settings.host_reserved_disk_gb - allocated_storage,
        )

    def ensure_fits(self, *, cpu: Decimal, memory_mb: int, storage_gb: int) -> None:
        free = self.allocatable()
        problems = []
        if cpu > free.cpu:
            problems.append(f"CPU: requested {cpu}, available {max(free.cpu, 0)}")
        if memory_mb > free.memory_mb:
            problems.append(f"memory: requested {memory_mb}MB, available {max(free.memory_mb, 0)}MB")
        if storage_gb > free.storage_gb:
            problems.append(f"storage: requested {storage_gb}GB, available {max(free.storage_gb, 0)}GB")
        if problems:
            raise HostCapacityError(
                "The host cannot fit this deployment right now — " + "; ".join(problems)
            )

    def usage_overview(self) -> dict:
        latest = self.metrics.latest()
        capacity = self.provider.host_capacity()
        allocated_cpu, allocated_mem, allocated_storage, _ = (
            self.deployments.allocated_resources()
        )
        free = self.allocatable()
        return {
            "cpu_percent": float(latest.cpu_percent) if latest else 0.0,
            "memory_used_mb": latest.memory_used_mb if latest else 0,
            "memory_total_mb": capacity.total_memory_mb,
            "disk_used_gb": float(capacity.used_disk_gb),
            "disk_total_gb": float(capacity.total_disk_gb),
            "running_containers": capacity.running_containers,
            "allocated_cpu": allocated_cpu,
            "allocated_memory_mb": allocated_mem,
            "allocated_storage_gb": allocated_storage,
            "allocatable_cpu": max(free.cpu, Decimal("0")),
            "allocatable_memory_mb": max(free.memory_mb, 0),
            "allocatable_storage_gb": max(free.storage_gb, 0),
            "sampled_at": latest.sampled_at if latest else None,
        }
