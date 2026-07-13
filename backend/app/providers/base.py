"""DeploymentProvider — the orchestrator abstraction.

Services and workers speak only this interface. `DockerProvider` implements it against
a local Docker Engine; a Kubernetes or remote-VM provider implements the same contract
without touching business logic. Specs are plain dataclasses (not ORM, not Pydantic)
so the provider layer has zero dependencies on web or persistence concerns.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class HealthcheckSpec:
    test: list[str]  # e.g. ["CMD-SHELL", "curl -f http://localhost/ || exit 1"]
    interval_s: int = 10
    timeout_s: int = 5
    retries: int = 3
    start_period_s: int = 10


@dataclass
class ServiceSpec:
    name: str
    image: str
    command: str | list[str] | None = None
    entrypoint: str | list[str] | None = None
    env: dict[str, str] = field(default_factory=dict)
    internal_port: int | None = None
    is_web: bool = False
    volumes: list[tuple[str, str]] = field(default_factory=list)  # (volume_name, mount_path)
    depends_on: list[str] = field(default_factory=list)
    healthcheck: HealthcheckSpec | None = None
    restart_policy: str = "unless-stopped"
    cpu_cores: Decimal = Decimal("0.5")
    memory_mb: int = 512


@dataclass
class DeploymentSpec:
    deployment_id: str
    owner_namespace: str  # e.g. "user12" — container name prefix
    slug: str  # unique subdomain label
    services: list[ServiceSpec] = field(default_factory=list)
    storage_gb: int = 1


@dataclass
class ServiceState:
    name: str
    container_id: str | None
    container_name: str | None
    status: str  # created|running|paused|restarting|exited|dead|missing
    restart_count: int = 0
    healthy: bool | None = None


@dataclass
class ServiceStats:
    name: str
    cpu_percent: float
    memory_used_mb: float
    memory_limit_mb: float
    network_rx_mb: float
    network_tx_mb: float
    status: str
    restart_count: int
    healthy: bool | None


@dataclass
class HostCapacity:
    total_cpu_cores: Decimal
    total_memory_mb: int
    total_disk_gb: Decimal
    used_disk_gb: Decimal
    cpu_percent: float
    memory_used_mb: int
    running_containers: int


class ProviderError(Exception):
    """Raised for any orchestrator-level failure; message is safe to persist."""


class DeploymentProvider(ABC):
    @abstractmethod
    def provision(self, spec: DeploymentSpec) -> list[ServiceState]:
        """Create isolation primitives and start every service. Idempotent-ish:
        implementations must clean up partial resources on failure."""

    @abstractmethod
    def start(self, deployment_id: str) -> list[ServiceState]:
        """Start a previously stopped deployment."""

    @abstractmethod
    def stop(self, deployment_id: str, timeout_s: int = 10) -> list[ServiceState]: ...

    @abstractmethod
    def restart(self, deployment_id: str, timeout_s: int = 10) -> list[ServiceState]: ...

    @abstractmethod
    def pause(self, deployment_id: str) -> list[ServiceState]: ...

    @abstractmethod
    def resume(self, deployment_id: str) -> list[ServiceState]: ...

    @abstractmethod
    def destroy(self, deployment_id: str, *, remove_volumes: bool = True) -> None:
        """Remove containers, networks and (optionally) volumes. Must succeed even
        when only part of the deployment exists."""

    @abstractmethod
    def status(self, deployment_id: str) -> list[ServiceState]: ...

    @abstractmethod
    def stats(self, deployment_id: str) -> list[ServiceStats]: ...

    @abstractmethod
    def logs(
        self,
        deployment_id: str,
        service_name: str | None = None,
        *,
        tail: int = 200,
        follow: bool = False,
    ) -> Iterator[str]: ...

    @abstractmethod
    def host_capacity(self) -> HostCapacity: ...

    @abstractmethod
    def list_managed_deployment_ids(self) -> set[str]:
        """Every deployment id the provider currently holds resources for
        (reconciliation input)."""
