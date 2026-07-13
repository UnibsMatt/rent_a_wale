"""Docker Engine implementation of DeploymentProvider.

Everything goes through the Docker SDK — no shell, no CLI, no subprocess. All created
objects (networks, volumes, containers) carry the platform labels from `naming.py`;
every read operation selects by label, so the provider is stateless.

Hard limits applied to every tenant container regardless of user input:
nano_cpus, mem_limit (+memswap = mem, i.e. swap disabled), pids_limit,
no-new-privileges, all capabilities dropped except a minimal functional set.
"""

from __future__ import annotations

import shutil
import time
from collections.abc import Iterator
from decimal import Decimal

import docker
from docker.errors import APIError, DockerException, ImageNotFound, NotFound
from docker.models.containers import Container

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.base import (
    DeploymentProvider,
    DeploymentSpec,
    HostCapacity,
    ProviderError,
    ServiceSpec,
    ServiceState,
    ServiceStats,
)
from app.providers.docker import naming
from app.providers.docker.compose_interpreter import startup_order

log = get_logger("app")

PIDS_LIMIT = 256
GRACE_STOP_SECONDS = 10
HEALTH_WAIT_SECONDS = 90
# Minimal capability set that lets mainstream official images (nginx, postgres, …)
# initialize as root and drop privileges, without granting anything host-dangerous.
SAFE_CAP_ADD = ["CHOWN", "DAC_OVERRIDE", "FOWNER", "SETGID", "SETUID", "SETFCAP", "KILL", "NET_BIND_SERVICE"]

_RESTART_POLICY_MAP = {
    "no": None,
    "always": {"Name": "always"},
    "on-failure": {"Name": "on-failure", "MaximumRetryCount": 5},
    "unless-stopped": {"Name": "unless-stopped"},
}


class DockerProvider(DeploymentProvider):
    def __init__(self, client: docker.DockerClient | None = None) -> None:
        try:
            self.client = client or docker.DockerClient(
                base_url=f"unix://{settings.docker_host_socket}", timeout=60
            )
        except DockerException as exc:
            raise ProviderError(f"Cannot connect to Docker engine: {exc}") from exc

    # ── helpers ──────────────────────────────────────────────────────────────

    def _containers(self, deployment_id: str, *, all: bool = True) -> list[Container]:
        return self.client.containers.list(
            all=all, filters={"label": f"{naming.DEPLOYMENT_LABEL}={deployment_id}"}
        )

    @staticmethod
    def _state(container: Container) -> ServiceState:
        attrs = container.attrs
        health = attrs.get("State", {}).get("Health", {}).get("Status")
        return ServiceState(
            name=container.labels.get(naming.SERVICE_LABEL, container.name),
            container_id=container.id,
            container_name=container.name,
            status=container.status,
            restart_count=attrs.get("RestartCount", 0),
            healthy=None if health is None else health == "healthy",
        )

    def _pull(self, image: str) -> None:
        repository, _, tag = image.partition("@")[0].rpartition(":")
        if not repository or "/" in tag:  # no tag present (or ':' was in registry host)
            repository, tag = image, "latest"
        try:
            self.client.images.pull(repository, tag=tag)
        except ImageNotFound as exc:
            raise ProviderError(f"Image not found: {image}") from exc
        except APIError as exc:
            raise ProviderError(f"Failed to pull {image}: {exc.explanation or exc}") from exc

    def _create_container(self, spec: DeploymentSpec, svc: ServiceSpec) -> Container:
        single = len(spec.services) == 1
        name = naming.container_name(spec.owner_namespace, spec.slug, svc.name, single=single)
        labels = naming.base_labels(spec.deployment_id, spec.owner_namespace)
        labels[naming.SERVICE_LABEL] = svc.name
        if svc.is_web and svc.internal_port:
            labels.update(
                naming.traefik_labels(
                    spec.deployment_id,
                    spec.slug,
                    settings.platform_domain,
                    svc.internal_port,
                    settings.traefik_tls,
                )
            )

        volumes = {
            naming.volume_name(spec.deployment_id, vol): {"bind": path, "mode": "rw"}
            for vol, path in svc.volumes
        }
        healthcheck = None
        if svc.healthcheck:
            healthcheck = {
                "test": svc.healthcheck.test,
                "interval": svc.healthcheck.interval_s * 1_000_000_000,
                "timeout": svc.healthcheck.timeout_s * 1_000_000_000,
                "retries": svc.healthcheck.retries,
                "start_period": svc.healthcheck.start_period_s * 1_000_000_000,
            }

        try:
            return self.client.containers.create(
                svc.image,
                command=svc.command,
                entrypoint=svc.entrypoint,
                name=name,
                hostname=svc.name,
                environment=svc.env,
                labels=labels,
                network=naming.network_name(spec.deployment_id),
                nano_cpus=int(Decimal(svc.cpu_cores) * 1_000_000_000),
                mem_limit=f"{svc.memory_mb}m",
                memswap_limit=f"{svc.memory_mb}m",  # equal to mem_limit → swap disabled
                pids_limit=PIDS_LIMIT,
                security_opt=["no-new-privileges:true"],
                cap_drop=["ALL"],
                cap_add=SAFE_CAP_ADD,
                restart_policy=_RESTART_POLICY_MAP[svc.restart_policy],
                healthcheck=healthcheck,
                volumes=volumes or None,
            )
        except APIError as exc:
            raise ProviderError(f"Failed to create {svc.name}: {exc.explanation or exc}") from exc

    def _wait_healthy(self, container: Container, timeout_s: int = HEALTH_WAIT_SECONDS) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            container.reload()
            health = container.attrs.get("State", {}).get("Health", {}).get("Status")
            if health is None or health == "healthy":
                return
            if health == "unhealthy":
                raise ProviderError(f"Service {container.name} became unhealthy during startup")
            if container.status in ("exited", "dead"):
                raise ProviderError(f"Service {container.name} exited during startup")
            time.sleep(2)
        raise ProviderError(f"Service {container.name} did not become healthy in {timeout_s}s")

    # ── lifecycle ────────────────────────────────────────────────────────────

    def provision(self, spec: DeploymentSpec) -> list[ServiceState]:
        try:
            return self._provision(spec)
        except Exception:
            # Never leave half a stack behind.
            self.destroy(spec.deployment_id, remove_volumes=True)
            raise

    def _provision(self, spec: DeploymentSpec) -> list[ServiceState]:
        for svc in spec.services:
            self._pull(svc.image)

        labels = naming.base_labels(spec.deployment_id, spec.owner_namespace)
        try:
            self.client.networks.create(
                naming.network_name(spec.deployment_id), driver="bridge", labels=labels
            )
        except APIError as exc:
            raise ProviderError(f"Failed to create network: {exc.explanation or exc}") from exc

        for svc in spec.services:
            for vol, _path in svc.volumes:
                self.client.volumes.create(
                    naming.volume_name(spec.deployment_id, vol), labels=labels
                )

        containers: dict[str, Container] = {}
        for svc in spec.services:
            containers[svc.name] = self._create_container(spec, svc)

        ingress = self.client.networks.get(settings.ingress_network)
        web = next((s for s in spec.services if s.is_web), None)
        if web is not None:
            ingress.connect(containers[web.name])

        for svc in startup_order(spec.services):
            container = containers[svc.name]
            try:
                container.start()
            except APIError as exc:
                raise ProviderError(
                    f"Failed to start {svc.name}: {exc.explanation or exc}"
                ) from exc
            # Gate dependents on health when the service defines a healthcheck.
            if svc.healthcheck and any(svc.name in s.depends_on for s in spec.services):
                self._wait_healthy(container)

        # Fail fast if something crashed immediately (bad command, missing env…).
        time.sleep(2)
        states = self.status(spec.deployment_id)
        crashed = [s for s in states if s.status in ("exited", "dead")]
        if crashed:
            raise ProviderError(
                "Service(s) exited immediately after start: "
                + ", ".join(s.name for s in crashed)
            )
        return states

    def start(self, deployment_id: str) -> list[ServiceState]:
        containers = self._containers(deployment_id)
        if not containers:
            raise ProviderError("No containers found for deployment")
        for c in containers:
            try:
                c.start()
            except APIError as exc:
                raise ProviderError(f"Failed to start {c.name}: {exc.explanation or exc}") from exc
        return self.status(deployment_id)

    def stop(self, deployment_id: str, timeout_s: int = GRACE_STOP_SECONDS) -> list[ServiceState]:
        for c in self._containers(deployment_id):
            try:
                c.stop(timeout=timeout_s)
            except NotFound:
                continue
            except APIError as exc:
                log.warning("stop_failed", container=c.name, error=str(exc))
                try:
                    c.kill()
                except APIError:
                    pass
        return self.status(deployment_id)

    def restart(self, deployment_id: str, timeout_s: int = GRACE_STOP_SECONDS) -> list[ServiceState]:
        for c in self._containers(deployment_id):
            try:
                c.restart(timeout=timeout_s)
            except APIError as exc:
                raise ProviderError(f"Failed to restart {c.name}: {exc.explanation or exc}") from exc
        return self.status(deployment_id)

    def pause(self, deployment_id: str) -> list[ServiceState]:
        for c in self._containers(deployment_id, all=False):
            try:
                c.pause()
            except APIError as exc:
                raise ProviderError(f"Failed to pause {c.name}: {exc.explanation or exc}") from exc
        return self.status(deployment_id)

    def resume(self, deployment_id: str) -> list[ServiceState]:
        for c in self._containers(deployment_id):
            if c.status == "paused":
                try:
                    c.unpause()
                except APIError as exc:
                    raise ProviderError(
                        f"Failed to resume {c.name}: {exc.explanation or exc}"
                    ) from exc
        return self.status(deployment_id)

    def destroy(self, deployment_id: str, *, remove_volumes: bool = True) -> None:
        """Best-effort teardown of everything labeled with this deployment id."""
        for c in self._containers(deployment_id):
            try:
                c.remove(force=True)
            except (NotFound, APIError) as exc:
                log.warning("destroy_container_failed", container=c.name, error=str(exc))
        label_filter = {"label": f"{naming.DEPLOYMENT_LABEL}={deployment_id}"}
        for network in self.client.networks.list(filters=label_filter):
            try:
                network.remove()
            except (NotFound, APIError) as exc:
                log.warning("destroy_network_failed", network=network.name, error=str(exc))
        if remove_volumes:
            for volume in self.client.volumes.list(filters=label_filter):
                try:
                    volume.remove(force=True)
                except (NotFound, APIError) as exc:
                    log.warning("destroy_volume_failed", volume=volume.name, error=str(exc))

    # ── observability ────────────────────────────────────────────────────────

    def status(self, deployment_id: str) -> list[ServiceState]:
        return [self._state(c) for c in self._containers(deployment_id)]

    def stats(self, deployment_id: str) -> list[ServiceStats]:
        out: list[ServiceStats] = []
        for c in self._containers(deployment_id):
            state = self._state(c)
            cpu = mem_used = mem_limit = rx = tx = 0.0
            if c.status == "running":
                try:
                    raw = c.stats(stream=False)
                    cpu = self._cpu_percent(raw)
                    mem_used = raw.get("memory_stats", {}).get("usage", 0) / (1024 * 1024)
                    mem_limit = raw.get("memory_stats", {}).get("limit", 0) / (1024 * 1024)
                    networks = raw.get("networks", {}) or {}
                    rx = sum(n.get("rx_bytes", 0) for n in networks.values()) / (1024 * 1024)
                    tx = sum(n.get("tx_bytes", 0) for n in networks.values()) / (1024 * 1024)
                except (APIError, KeyError) as exc:
                    log.warning("stats_failed", container=c.name, error=str(exc))
            out.append(
                ServiceStats(
                    name=state.name,
                    cpu_percent=round(cpu, 2),
                    memory_used_mb=round(mem_used, 1),
                    memory_limit_mb=round(mem_limit, 1),
                    network_rx_mb=round(rx, 2),
                    network_tx_mb=round(tx, 2),
                    status=state.status,
                    restart_count=state.restart_count,
                    healthy=state.healthy,
                )
            )
        return out

    @staticmethod
    def _cpu_percent(raw: dict) -> float:
        try:
            cpu_stats = raw["cpu_stats"]
            pre = raw["precpu_stats"]
            cpu_delta = cpu_stats["cpu_usage"]["total_usage"] - pre["cpu_usage"]["total_usage"]
            sys_delta = cpu_stats.get("system_cpu_usage", 0) - pre.get("system_cpu_usage", 0)
            online = cpu_stats.get("online_cpus") or len(
                cpu_stats["cpu_usage"].get("percpu_usage") or [1]
            )
            if sys_delta > 0 and cpu_delta >= 0:
                return (cpu_delta / sys_delta) * online * 100.0
        except (KeyError, ZeroDivisionError):
            pass
        return 0.0

    def logs(
        self,
        deployment_id: str,
        service_name: str | None = None,
        *,
        tail: int = 200,
        follow: bool = False,
    ) -> Iterator[str]:
        containers = self._containers(deployment_id)
        if service_name is not None:
            containers = [
                c for c in containers if c.labels.get(naming.SERVICE_LABEL) == service_name
            ]
            if not containers:
                raise ProviderError(f"Unknown service {service_name!r}")
        if follow:
            # Follow a single stream: the requested service, else the web/first one.
            target = containers[0]
            for chunk in target.logs(stream=True, follow=True, tail=tail, timestamps=True):
                yield chunk.decode("utf-8", errors="replace")
            return
        for c in containers:
            prefix = c.labels.get(naming.SERVICE_LABEL, c.name)
            try:
                text = c.logs(tail=tail, timestamps=True).decode("utf-8", errors="replace")
            except APIError as exc:
                text = f"<logs unavailable: {exc.explanation or exc}>\n"
            for line in text.splitlines():
                yield f"[{prefix}] {line}\n"

    def host_capacity(self) -> HostCapacity:
        try:
            info = self.client.info()
        except APIError as exc:
            raise ProviderError(f"Docker info failed: {exc}") from exc
        disk = shutil.disk_usage("/")
        running = self.client.containers.list(
            filters={"label": f"{naming.MANAGED_LABEL}=true", "status": "running"}
        )
        mem_total_mb = int(info.get("MemTotal", 0) / (1024 * 1024))
        return HostCapacity(
            total_cpu_cores=Decimal(info.get("NCPU", 0)),
            total_memory_mb=mem_total_mb,
            total_disk_gb=Decimal(disk.total) / (1024**3),
            used_disk_gb=Decimal(disk.used) / (1024**3),
            cpu_percent=0.0,  # sampled by the metrics worker, not per call
            memory_used_mb=0,
            running_containers=len(running),
        )

    def list_managed_deployment_ids(self) -> set[str]:
        containers = self.client.containers.list(
            all=True, filters={"label": f"{naming.MANAGED_LABEL}=true"}
        )
        return {
            c.labels[naming.DEPLOYMENT_LABEL]
            for c in containers
            if naming.DEPLOYMENT_LABEL in c.labels
        }
