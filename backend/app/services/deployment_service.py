"""Deployment orchestration business logic.

The API-side service validates, reserves (quota/capacity/funds), persists the
deployment in `pending`, emits the `created` event, and enqueues the async provision
task. All Docker work happens in workers through the provider abstraction.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from decimal import Decimal

from sqlalchemy.orm import Session

from app.billing import pricing
from app.core.config import settings
from app.core.exceptions import (
    ConflictError,
    InsufficientCreditsError,
    NotFoundError,
    PermissionDeniedError,
    QuotaExceededError,
    ValidationFailedError,
)
from app.events import emitter
from app.models import Deployment, DeploymentService as DeploymentServiceRow, User
from app.models.enums import DeploymentEventType, DeploymentKind, DeploymentStatus
from app.providers import get_provider
from app.providers.base import DeploymentSpec, HealthcheckSpec, ServiceSpec
from app.providers.docker.compose_interpreter import parse_compose
from app.repositories.billing import PricingRepository
from app.repositories.deployments import DeploymentRepository
from app.repositories.users import CreditAccountRepository, UserRepository
from app.schemas.deployment import DeploymentCreate, EstimateRequest, ImageSpec, ResourceSpec
from app.services.audit_service import AuditService
from app.services.host_service import HostService
from app.services.image_policy import ImagePolicyService
from app.utils.slug import random_suffix, slugify

# Statuses from which each action is legal.
STOPPABLE = (DeploymentStatus.RUNNING, DeploymentStatus.PROVISIONING)
STARTABLE = (DeploymentStatus.STOPPED, DeploymentStatus.CREDIT_EXHAUSTED)
DELETABLE = tuple(s for s in DeploymentStatus if s not in (DeploymentStatus.DELETING, DeploymentStatus.DELETED))

TASKS = {
    "provision": "app.workers.tasks.provision_deployment",
    "stop": "app.workers.tasks.stop_deployment",
    "start": "app.workers.tasks.start_deployment",
    "restart": "app.workers.tasks.restart_deployment",
    "delete": "app.workers.tasks.delete_deployment",
}


def _enqueue(task: str, *args: str) -> None:
    from app.workers.celery_app import celery_app

    celery_app.send_task(TASKS[task], args=list(args))


# ── Spec (de)serialization: DB JSON ⇄ provider dataclasses ───────────────────


def services_to_spec_dict(services: list[ServiceSpec], storage_gb: int) -> dict:
    return {
        "storage_gb": storage_gb,
        "services": [
            {
                "name": s.name,
                "image": s.image,
                "command": s.command,
                "entrypoint": s.entrypoint,
                "env": s.env,
                "internal_port": s.internal_port,
                "is_web": s.is_web,
                "volumes": [list(v) for v in s.volumes],
                "depends_on": s.depends_on,
                "healthcheck": (
                    {
                        "test": s.healthcheck.test,
                        "interval_s": s.healthcheck.interval_s,
                        "timeout_s": s.healthcheck.timeout_s,
                        "retries": s.healthcheck.retries,
                        "start_period_s": s.healthcheck.start_period_s,
                    }
                    if s.healthcheck
                    else None
                ),
                "restart_policy": s.restart_policy,
                "cpu_cores": str(s.cpu_cores),
                "memory_mb": s.memory_mb,
            }
            for s in services
        ],
    }


def spec_dict_to_provider_spec(deployment: Deployment, owner_namespace: str) -> DeploymentSpec:
    services = []
    for s in deployment.spec["services"]:
        hc = s.get("healthcheck")
        services.append(
            ServiceSpec(
                name=s["name"],
                image=s["image"],
                command=s.get("command"),
                entrypoint=s.get("entrypoint"),
                env=s.get("env", {}),
                internal_port=s.get("internal_port"),
                is_web=s.get("is_web", False),
                volumes=[tuple(v) for v in s.get("volumes", [])],
                depends_on=s.get("depends_on", []),
                healthcheck=HealthcheckSpec(**hc) if hc else None,
                restart_policy=s.get("restart_policy", "unless-stopped"),
                cpu_cores=Decimal(s["cpu_cores"]),
                memory_mb=s["memory_mb"],
            )
        )
    return DeploymentSpec(
        deployment_id=str(deployment.id),
        owner_namespace=owner_namespace,
        slug=deployment.slug,
        services=services,
        storage_gb=deployment.spec.get("storage_gb", 1),
    )


class DeploymentOrchestrationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = DeploymentRepository(db)
        self.users = UserRepository(db)
        self.accounts = CreditAccountRepository(db)
        self.pricing = PricingRepository(db)
        self.images = ImagePolicyService(db)
        self.host = HostService(db)
        self.audit = AuditService(db)

    # ── Estimation ───────────────────────────────────────────────────────────

    def _active_snapshot(self) -> dict:
        plan = self.pricing.active_plan()
        if plan is None:
            raise ValidationFailedError("No active pricing plan configured")
        return plan.snapshot()

    def estimate(self, request: EstimateRequest) -> dict:
        snapshot = self._active_snapshot()
        hourly = pricing.hourly_cost(
            snapshot,
            cpu_cores=request.resources.cpu_cores,
            memory_mb=request.resources.memory_mb,
            storage_gb=request.resources.storage_gb,
            service_count=request.service_count,
        )
        return {
            "hourly": hourly,
            "daily": hourly * pricing.HOURS_PER_DAY,
            "monthly": hourly * pricing.HOURS_PER_MONTH,
            "plan_name": snapshot["plan_name"],
            "breakdown": pricing.cost_breakdown(
                snapshot,
                cpu_cores=request.resources.cpu_cores,
                memory_mb=request.resources.memory_mb,
                storage_gb=request.resources.storage_gb,
                service_count=request.service_count,
            ),
        }

    # ── Compose validation (wizard step) ────────────────────────────────────

    def validate_compose(self, compose_yaml: str) -> dict:
        parsed = parse_compose(compose_yaml)
        errors = list(parsed.errors)
        for svc in parsed.services:
            try:
                self.images.check(svc.image)
            except ValidationFailedError as exc:
                errors.append(exc.message)
        services = [
            {
                "name": s.name,
                "image": s.image,
                "web_port": s.internal_port if s.is_web else None,
                "cpu_cores": s.cpu_cores,
                "memory_mb": s.memory_mb,
                "env_keys": sorted(s.env.keys()),
                "volumes": [f"{v[0]}:{v[1]}" for v in s.volumes],
                "depends_on": s.depends_on,
            }
            for s in parsed.services
        ]
        aggregate = None
        if parsed.services:
            aggregate = ResourceSpec(
                cpu_cores=parsed.total_cpu,
                memory_mb=max(parsed.total_memory_mb, 64),
                storage_gb=1,
            )
        return {"valid": not errors, "errors": errors, "services": services, "aggregate": aggregate}

    # ── Creation ─────────────────────────────────────────────────────────────

    def _build_services(self, payload: DeploymentCreate) -> list[ServiceSpec]:
        if payload.kind == DeploymentKind.IMAGE:
            if payload.image_spec is None:
                raise ValidationFailedError("image_spec is required for image deployments")
            spec: ImageSpec = payload.image_spec
            self.images.check(spec.image)
            return [
                ServiceSpec(
                    name="app",
                    image=spec.image,
                    command=spec.command,
                    env=spec.env,
                    internal_port=spec.web_port,
                    is_web=spec.web_port is not None,
                    volumes=[(v.name, v.container_path) for v in spec.volumes],
                    restart_policy=spec.restart_policy,
                    cpu_cores=payload.resources.cpu_cores,
                    memory_mb=payload.resources.memory_mb,
                )
            ]
        if payload.compose_yaml is None:
            raise ValidationFailedError("compose_yaml is required for compose deployments")
        parsed = parse_compose(payload.compose_yaml)
        if not parsed.valid:
            raise ValidationFailedError(
                "Compose validation failed", detail={"errors": parsed.errors}
            )
        for svc in parsed.services:
            self.images.check(svc.image)
        return parsed.services

    def _unique_slug(self, payload: DeploymentCreate) -> str:
        if payload.hostname:
            if self.repo.slug_exists(payload.hostname):
                raise ConflictError(f"Hostname {payload.hostname!r} is already taken")
            return payload.hostname
        base = slugify(payload.name)
        for _ in range(20):
            candidate = f"{base}-{random_suffix()}"
            if not self.repo.slug_exists(candidate):
                return candidate
        raise ConflictError("Could not allocate a unique hostname, try a custom one")

    def create(self, *, user: User, payload: DeploymentCreate, ip: str) -> Deployment:
        services = self._build_services(payload)

        # Aggregate resources: user-specified for single image, summed for compose.
        if payload.kind == DeploymentKind.COMPOSE:
            cpu = sum((s.cpu_cores for s in services), Decimal("0"))
            memory_mb = sum(s.memory_mb for s in services)
        else:
            cpu = payload.resources.cpu_cores
            memory_mb = payload.resources.memory_mb
        storage_gb = payload.resources.storage_gb

        # 1. Per-user quotas.
        account = self.accounts.get_by_user_for_update(user.id)
        if account is None:
            raise NotFoundError("Credit account not found")
        used_cpu, used_mem, used_storage, used_count = self.repo.allocated_resources(user.id)
        if used_count + 1 > account.max_deployments_quota:
            raise QuotaExceededError("Deployment count quota exceeded")
        if used_cpu + cpu > account.max_cpu_quota:
            raise QuotaExceededError(
                f"CPU quota exceeded ({used_cpu + cpu} > {account.max_cpu_quota} cores)"
            )
        if used_mem + memory_mb > account.max_memory_mb_quota:
            raise QuotaExceededError("Memory quota exceeded")
        if used_storage + storage_gb > account.max_storage_gb_quota:
            raise QuotaExceededError("Storage quota exceeded")

        # 2. Host capacity.
        self.host.ensure_fits(cpu=cpu, memory_mb=memory_mb, storage_gb=storage_gb)

        # 3. Funds: require at least `min_balance_hours` of runtime up front.
        snapshot = self._active_snapshot()
        hourly = pricing.hourly_cost(
            snapshot, cpu_cores=cpu, memory_mb=memory_mb,
            storage_gb=storage_gb, service_count=len(services),
        )
        required = hourly * Decimal(str(settings.min_balance_hours))
        if account.balance < required:
            raise InsufficientCreditsError(
                f"Insufficient credits: this deployment costs {hourly}/hour and requires "
                f"a balance of at least {required} (you have {account.balance})"
            )

        # 4. Persist in `pending` + outbox event, then enqueue.
        slug = self._unique_slug(payload)
        deployment = self.repo.add(
            Deployment(
                owner_id=user.id,
                name=payload.name,
                slug=slug,
                kind=payload.kind,
                status=DeploymentStatus.PENDING,
                cpu_cores=cpu,
                memory_mb=memory_mb,
                storage_gb=storage_gb,
                spec=services_to_spec_dict(services, storage_gb),
                price_snapshot=snapshot,
                estimated_hourly_cost=hourly,
                template_id=payload.template_id,
            )
        )
        for s in services:
            self.repo.add_service(
                DeploymentServiceRow(
                    deployment_id=deployment.id,
                    service_name=s.name,
                    image=s.image,
                    is_web=s.is_web,
                    internal_port=s.internal_port,
                )
            )
        event = emitter.emit(
            self.db, deployment.id, DeploymentEventType.CREATED,
            {"owner_id": str(user.id), "hourly_cost": str(hourly)},
        )
        self.audit.record(
            actor_id=user.id, action="deployment.create", resource_type="deployment",
            resource_id=str(deployment.id), ip_address=ip,
            detail={"kind": payload.kind, "slug": slug},
        )
        self.db.commit()
        emitter.kick([event.id])
        _enqueue("provision", str(deployment.id))
        return deployment

    # ── Read paths ───────────────────────────────────────────────────────────

    def get_authorized(self, *, user: User, deployment_id: uuid.UUID) -> Deployment:
        deployment = self.repo.get(deployment_id)
        if deployment is None or deployment.deleted_at is not None:
            raise NotFoundError("Deployment not found")
        if deployment.owner_id != user.id and not user.is_admin:
            raise PermissionDeniedError("You do not own this deployment")
        return deployment

    def list_for_user(self, user: User) -> list[Deployment]:
        return self.repo.list_for_owner(user.id)

    def stats(self, *, user: User, deployment_id: uuid.UUID) -> list:
        deployment = self.get_authorized(user=user, deployment_id=deployment_id)
        if deployment.status != DeploymentStatus.RUNNING:
            return []
        return get_provider().stats(str(deployment.id))

    def container_logs(
        self, *, user: User, deployment_id: uuid.UUID,
        service: str | None, tail: int, follow: bool,
    ) -> Iterator[str]:
        deployment = self.get_authorized(user=user, deployment_id=deployment_id)
        return get_provider().logs(str(deployment.id), service, tail=tail, follow=follow)

    def platform_logs(self, *, user: User, deployment_id: uuid.UUID) -> list:
        deployment = self.get_authorized(user=user, deployment_id=deployment_id)
        return self.repo.logs_for(deployment.id)

    def events(self, *, user: User, deployment_id: uuid.UUID) -> list:
        deployment = self.get_authorized(user=user, deployment_id=deployment_id)
        return self.repo.events_for(deployment.id)

    def total_spent(self, deployment_id: uuid.UUID) -> Decimal:
        return self.repo.total_credits_spent(deployment_id)

    # ── Lifecycle actions (enqueue; workers do the Docker work) ─────────────

    def _transition(
        self, *, user: User, deployment_id: uuid.UUID, ip: str,
        allowed_from: tuple, interim: DeploymentStatus,
        event_type: DeploymentEventType, task: str, action: str,
    ) -> Deployment:
        deployment = self.get_authorized(user=user, deployment_id=deployment_id)
        locked = self.repo.get_for_update(deployment.id)
        assert locked is not None
        if locked.status not in allowed_from:
            raise ConflictError(
                f"Cannot {action} a deployment in status {locked.status!r}"
            )
        locked.status = interim
        event = emitter.emit(self.db, locked.id, event_type, {"actor_id": str(user.id)})
        self.audit.record(
            actor_id=user.id, action=f"deployment.{action}", resource_type="deployment",
            resource_id=str(locked.id), ip_address=ip,
        )
        self.db.commit()
        emitter.kick([event.id])
        _enqueue(task, str(locked.id))
        return locked

    def stop(self, *, user: User, deployment_id: uuid.UUID, ip: str) -> Deployment:
        return self._transition(
            user=user, deployment_id=deployment_id, ip=ip,
            allowed_from=STOPPABLE, interim=DeploymentStatus.STOPPING,
            event_type=DeploymentEventType.STOPPING, task="stop", action="stop",
        )

    def start(self, *, user: User, deployment_id: uuid.UUID, ip: str) -> Deployment:
        # Restarting after credit exhaustion requires funds again.
        deployment = self.get_authorized(user=user, deployment_id=deployment_id)
        account = self.accounts.get_by_user(deployment.owner_id)
        required = deployment.estimated_hourly_cost * Decimal(str(settings.min_balance_hours))
        if account is None or account.balance < required:
            raise InsufficientCreditsError(
                f"Balance of at least {required} required to start (hourly cost "
                f"{deployment.estimated_hourly_cost})"
            )
        return self._transition(
            user=user, deployment_id=deployment_id, ip=ip,
            allowed_from=STARTABLE, interim=DeploymentStatus.PROVISIONING,
            event_type=DeploymentEventType.PROVISIONING, task="start", action="start",
        )

    def restart(self, *, user: User, deployment_id: uuid.UUID, ip: str) -> Deployment:
        return self._transition(
            user=user, deployment_id=deployment_id, ip=ip,
            allowed_from=(DeploymentStatus.RUNNING,), interim=DeploymentStatus.PROVISIONING,
            event_type=DeploymentEventType.PROVISIONING, task="restart", action="restart",
        )

    def delete(self, *, user: User, deployment_id: uuid.UUID, ip: str) -> Deployment:
        return self._transition(
            user=user, deployment_id=deployment_id, ip=ip,
            allowed_from=DELETABLE, interim=DeploymentStatus.DELETING,
            event_type=DeploymentEventType.STOPPING, task="delete", action="delete",
        )

    def pause(self, *, user: User, deployment_id: uuid.UUID, ip: str) -> list:
        deployment = self.get_authorized(user=user, deployment_id=deployment_id)
        if deployment.status != DeploymentStatus.RUNNING:
            raise ConflictError("Only running deployments can be paused")
        states = get_provider().pause(str(deployment.id))
        self.audit.record(
            actor_id=user.id, action="deployment.pause", resource_type="deployment",
            resource_id=str(deployment.id), ip_address=ip,
        )
        self.db.commit()
        return states

    def resume(self, *, user: User, deployment_id: uuid.UUID, ip: str) -> list:
        deployment = self.get_authorized(user=user, deployment_id=deployment_id)
        states = get_provider().resume(str(deployment.id))
        self.audit.record(
            actor_id=user.id, action="deployment.resume", resource_type="deployment",
            resource_id=str(deployment.id), ip_address=ip,
        )
        self.db.commit()
        return states
