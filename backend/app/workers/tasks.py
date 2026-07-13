"""Celery tasks: deployment lifecycle, event consumers, billing tick, reconciler,
host metrics. Every task opens its own session scope; consumers are idempotent
because delivery is at-least-once."""

from __future__ import annotations

import shutil
import time
import uuid
from datetime import UTC, datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.billing import pricing
from app.core.config import settings
from app.core.db import session_scope
from app.core.logging import get_logger
from app.events import emitter
from app.models import CreditTransaction, DeploymentLog, HostMetric, UsageRecord
from app.models.enums import (
    DeploymentEventType,
    DeploymentStatus,
    LogSource,
    TransactionKind,
)
from app.providers import get_provider
from app.providers.base import ProviderError
from app.repositories.billing import UsageRepository
from app.repositories.deployments import DeploymentRepository
from app.repositories.governance import MetricsRepository
from app.repositories.users import CreditAccountRepository, UserRepository
from app.services.audit_service import AuditService
from app.services.deployment_service import spec_dict_to_provider_spec
from app.workers.celery_app import celery_app

log = get_logger("app")
billing_log = get_logger("billing")


def _dep_log(db: Session, deployment_id: uuid.UUID, message: str,
             source: str = LogSource.SYSTEM, level: str = "info") -> None:
    db.add(DeploymentLog(deployment_id=deployment_id, source=source, level=level, message=message))


def _set_status(db: Session, deployment, status: DeploymentStatus,
                event: DeploymentEventType, payload: dict | None = None) -> uuid.UUID:
    deployment.status = status
    return emitter.emit(db, deployment.id, event, payload or {}).id


# ── Lifecycle ────────────────────────────────────────────────────────────────


@celery_app.task(name="app.workers.tasks.provision_deployment", bind=True, max_retries=0)
def provision_deployment(self, deployment_id: str) -> None:
    events: list[uuid.UUID] = []
    with session_scope() as db:
        repo = DeploymentRepository(db)
        deployment = repo.get_for_update(uuid.UUID(deployment_id))
        if deployment is None or deployment.status not in (
            DeploymentStatus.PENDING, DeploymentStatus.PROVISIONING,
        ):
            return
        owner = UserRepository(db).get(deployment.owner_id)
        events.append(_set_status(
            db, deployment, DeploymentStatus.PROVISIONING, DeploymentEventType.PROVISIONING
        ))
        _dep_log(db, deployment.id, "Provisioning started: pulling images and creating resources")
        spec = spec_dict_to_provider_spec(deployment, owner.container_namespace)
    emitter.kick(events)
    events.clear()

    provider = get_provider()
    try:
        states = provider.provision(spec)
        error = None
    except ProviderError as exc:
        states, error = [], str(exc)
    except Exception as exc:  # unexpected — never leave the row in provisioning
        log.exception("provision_unexpected_failure", deployment_id=deployment_id)
        states, error = [], f"Unexpected provisioning error: {exc}"

    with session_scope() as db:
        repo = DeploymentRepository(db)
        deployment = repo.get_for_update(uuid.UUID(deployment_id))
        if deployment is None:
            return
        if deployment.status == DeploymentStatus.DELETING:
            # User deleted mid-provision; the delete task owns teardown.
            return
        if error is not None:
            deployment.failure_reason = error
            events.append(_set_status(
                db, deployment, DeploymentStatus.FAILED,
                DeploymentEventType.FAILED, {"reason": error},
            ))
            _dep_log(db, deployment.id, f"Provisioning failed: {error}", level="error")
        else:
            by_name = {s.name: s for s in states}
            for row in repo.services_for(deployment.id):
                state = by_name.get(row.service_name)
                if state:
                    row.container_id = state.container_id
                    row.container_name = state.container_name
                    row.status = state.status
                    row.restart_count = state.restart_count
            deployment.started_at = datetime.now(UTC)
            web = next((s for s in spec.services if s.is_web), None)
            if web is not None:
                deployment.public_url = (
                    f"{settings.deployment_url_scheme}://{deployment.slug}.{settings.platform_domain}"
                )
            events.append(_set_status(
                db, deployment, DeploymentStatus.RUNNING, DeploymentEventType.RUNNING,
                {"public_url": deployment.public_url},
            ))
            _dep_log(db, deployment.id, "Deployment is running"
                     + (f" at {deployment.public_url}" if deployment.public_url else ""))
    emitter.kick(events)


def _finalize_stop(deployment_id: str, *, reason: str | None) -> None:
    provider = get_provider()
    try:
        provider.stop(deployment_id)
    except ProviderError as exc:
        log.warning("stop_provider_error", deployment_id=deployment_id, error=str(exc))
    events: list[uuid.UUID] = []
    with session_scope() as db:
        repo = DeploymentRepository(db)
        deployment = repo.get_for_update(uuid.UUID(deployment_id))
        if deployment is None:
            return
        deployment.stopped_at = datetime.now(UTC)
        if reason == "credit_exhausted":
            events.append(_set_status(
                db, deployment, DeploymentStatus.CREDIT_EXHAUSTED,
                DeploymentEventType.STOPPED, {"reason": reason},
            ))
            _dep_log(db, deployment.id,
                     "Deployment stopped automatically: credits exhausted",
                     source=LogSource.BILLING, level="warning")
        else:
            events.append(_set_status(
                db, deployment, DeploymentStatus.STOPPED, DeploymentEventType.STOPPED,
                {"reason": reason or "user_requested"},
            ))
            _dep_log(db, deployment.id, "Deployment stopped")
    emitter.kick(events)


@celery_app.task(name="app.workers.tasks.stop_deployment")
def stop_deployment(deployment_id: str, reason: str | None = None) -> None:
    _finalize_stop(deployment_id, reason=reason)


@celery_app.task(name="app.workers.tasks.start_deployment")
def start_deployment(deployment_id: str) -> None:
    provider = get_provider()
    events: list[uuid.UUID] = []
    try:
        provider.start(deployment_id)
        error = None
    except ProviderError as exc:
        error = str(exc)
    with session_scope() as db:
        repo = DeploymentRepository(db)
        deployment = repo.get_for_update(uuid.UUID(deployment_id))
        if deployment is None:
            return
        if error is not None:
            deployment.failure_reason = error
            events.append(_set_status(
                db, deployment, DeploymentStatus.FAILED, DeploymentEventType.FAILED,
                {"reason": error},
            ))
            _dep_log(db, deployment.id, f"Start failed: {error}", level="error")
        else:
            deployment.started_at = datetime.now(UTC)
            deployment.stopped_at = None
            events.append(_set_status(
                db, deployment, DeploymentStatus.RUNNING, DeploymentEventType.RUNNING, {}
            ))
            _dep_log(db, deployment.id, "Deployment started")
    emitter.kick(events)


@celery_app.task(name="app.workers.tasks.restart_deployment")
def restart_deployment(deployment_id: str) -> None:
    provider = get_provider()
    events: list[uuid.UUID] = []
    try:
        provider.restart(deployment_id)
        error = None
    except ProviderError as exc:
        error = str(exc)
    with session_scope() as db:
        repo = DeploymentRepository(db)
        deployment = repo.get_for_update(uuid.UUID(deployment_id))
        if deployment is None:
            return
        if error is not None:
            deployment.failure_reason = error
            events.append(_set_status(
                db, deployment, DeploymentStatus.FAILED, DeploymentEventType.FAILED,
                {"reason": error},
            ))
        else:
            events.append(_set_status(
                db, deployment, DeploymentStatus.RUNNING, DeploymentEventType.RUNNING, {}
            ))
            _dep_log(db, deployment.id, "Deployment restarted")
    emitter.kick(events)


@celery_app.task(name="app.workers.tasks.delete_deployment")
def delete_deployment(deployment_id: str) -> None:
    provider = get_provider()
    try:
        provider.destroy(deployment_id, remove_volumes=True)
    except ProviderError as exc:
        log.warning("destroy_provider_error", deployment_id=deployment_id, error=str(exc))
    events: list[uuid.UUID] = []
    with session_scope() as db:
        repo = DeploymentRepository(db)
        deployment = repo.get_for_update(uuid.UUID(deployment_id))
        if deployment is None:
            return
        deployment.deleted_at = datetime.now(UTC)
        deployment.stopped_at = deployment.stopped_at or datetime.now(UTC)
        events.append(_set_status(
            db, deployment, DeploymentStatus.DELETED, DeploymentEventType.DELETED, {}
        ))
        _dep_log(db, deployment.id, "Deployment deleted; containers, network and volumes removed")
    emitter.kick(events)


# ── Event consumers (billing / audit / notifications) ───────────────────────


@celery_app.task(name="app.workers.tasks.handle_event", bind=True, max_retries=3)
def handle_event(self, event_id: str) -> None:
    with session_scope() as db:
        repo = DeploymentRepository(db)
        event = repo.get_event(uuid.UUID(event_id))
        if event is None or event.dispatched:
            return
        deployment = repo.get(event.deployment_id)

        # Consumer 1: billing bookkeeping lines.
        if deployment is not None and event.event_type == DeploymentEventType.RUNNING:
            billing_log.info(
                "metering_active", deployment_id=str(deployment.id),
                hourly_cost=str(deployment.estimated_hourly_cost),
            )
        if deployment is not None and event.event_type in (
            DeploymentEventType.STOPPED, DeploymentEventType.DELETED,
        ):
            total = repo.total_credits_spent(deployment.id)
            _dep_log(db, deployment.id,
                     f"Total credits spent on this deployment so far: {total}",
                     source=LogSource.BILLING)

        # Consumer 2: audit trail (system actor).
        AuditService(db).record(
            actor_id=None, action=f"deployment.event.{event.event_type}",
            resource_type="deployment", resource_id=str(event.deployment_id),
            detail=event.payload,
        )

        # Consumer 3: notifications placeholder (email/webhook integration point).
        log.info("notification_placeholder", event=event.event_type,
                 deployment_id=str(event.deployment_id))

        event.dispatched = True


@celery_app.task(name="app.workers.tasks.relay_outbox")
def relay_outbox() -> None:
    """Safety net: dispatch events whose post-commit kick was lost."""
    with session_scope() as db:
        pending = DeploymentRepository(db).undispatched_events()
        ids = [e.id for e in pending]
    if ids:
        log.info("outbox_relay", count=len(ids))
        emitter.kick(ids)


# ── Billing tick ─────────────────────────────────────────────────────────────


@celery_app.task(name="app.workers.tasks.billing_tick")
def billing_tick() -> None:
    tick = settings.billing_tick_seconds
    now = datetime.now(UTC)
    epoch = int(now.timestamp())
    period_start = datetime.fromtimestamp(epoch - (epoch % tick), tz=timezone.utc)
    period_end = datetime.fromtimestamp(epoch - (epoch % tick) + tick, tz=timezone.utc)

    with session_scope() as db:
        running_ids = [d.id for d in DeploymentRepository(db).list_by_status(DeploymentStatus.RUNNING)]

    for deployment_id in running_ids:
        try:
            _bill_deployment(deployment_id, period_start, period_end, tick)
        except Exception:
            log.exception("billing_tick_failed", deployment_id=str(deployment_id))


def _bill_deployment(deployment_id: uuid.UUID, period_start: datetime,
                     period_end: datetime, tick_seconds: int) -> None:
    exhausted = False
    with session_scope() as db:
        repo = DeploymentRepository(db)
        usage = UsageRepository(db)
        accounts = CreditAccountRepository(db)

        deployment = repo.get_for_update(deployment_id)
        if deployment is None or deployment.status != DeploymentStatus.RUNNING:
            return
        if usage.period_exists(deployment.id, period_start):
            return  # idempotent: this period is already billed

        account = accounts.get_by_user_for_update(deployment.owner_id)
        if account is None:
            log.error("billing_no_account", deployment_id=str(deployment_id))
            return

        cost = pricing.period_cost(deployment.estimated_hourly_cost, tick_seconds)
        charge = min(cost, account.balance)

        usage.add(UsageRecord(
            deployment_id=deployment.id,
            period_start=period_start,
            period_end=period_end,
            credits_charged=charge,
            price_snapshot=deployment.price_snapshot,
        ))
        if charge > 0:
            account.balance -= charge
            db.add(CreditTransaction(
                account_id=account.id,
                kind=TransactionKind.USAGE,
                amount=-charge,
                balance_after=account.balance,
                deployment_id=deployment.id,
            ))
        billing_log.info(
            "billed", deployment_id=str(deployment.id), charged=str(charge),
            balance=str(account.balance),
        )

        if account.balance < pricing.period_cost(deployment.estimated_hourly_cost, tick_seconds):
            exhausted = True
            event = emitter.emit(
                db, deployment.id, DeploymentEventType.CREDIT_EXHAUSTED,
                {"balance": str(account.balance)},
            )
            _dep_log(db, deployment.id,
                     "Credits exhausted — stopping deployment",
                     source=LogSource.BILLING, level="warning")
            event_id = event.id
    if exhausted:
        emitter.kick([event_id])
        celery_app.send_task(
            "app.workers.tasks.stop_deployment",
            args=[str(deployment_id)], kwargs={"reason": "credit_exhausted"},
        )


# ── Reconciler ───────────────────────────────────────────────────────────────


@celery_app.task(name="app.workers.tasks.reconcile_deployments")
def reconcile_deployments() -> None:
    provider = get_provider()
    try:
        managed_ids = provider.list_managed_deployment_ids()
    except ProviderError as exc:
        log.warning("reconcile_provider_unavailable", error=str(exc))
        return

    events: list[uuid.UUID] = []
    with session_scope() as db:
        repo = DeploymentRepository(db)

        # 1. DB says RUNNING — verify against reality; sync service states.
        for deployment in repo.list_by_status(DeploymentStatus.RUNNING):
            states = provider.status(str(deployment.id))
            by_name = {s.name: s for s in states}
            for row in repo.services_for(deployment.id):
                state = by_name.get(row.service_name)
                if state:
                    row.status = state.status
                    row.restart_count = state.restart_count
                    row.container_id = state.container_id
            alive = [s for s in states if s.status in ("running", "restarting", "paused")]
            if not alive:
                reason = ("containers missing from engine" if not states
                          else "all containers exited")
                deployment.failure_reason = reason
                deployment.stopped_at = datetime.now(UTC)
                events.append(_set_status(
                    db, deployment, DeploymentStatus.FAILED, DeploymentEventType.FAILED,
                    {"reason": f"reconciler: {reason}"},
                ))
                _dep_log(db, deployment.id, f"Reconciler marked deployment failed: {reason}",
                         level="error")

        # 2. Engine holds resources for ids the DB considers gone → orphans.
        active_ids = {str(d.id) for d in repo.list_active()} | {
            str(d.id) for d in repo.list_by_status(DeploymentStatus.STOPPED)
        } | {str(d.id) for d in repo.list_by_status(DeploymentStatus.CREDIT_EXHAUSTED)} | {
            str(d.id) for d in repo.list_by_status(DeploymentStatus.FAILED)
        }
        orphans = managed_ids - active_ids
        for orphan_id in orphans:
            log.warning("reconcile_orphan_destroy", deployment_id=orphan_id)
            AuditService(db).record(
                actor_id=None, action="reconciler.orphan_destroyed",
                resource_type="deployment", resource_id=orphan_id,
            )
    for orphan_id in orphans:
        try:
            provider.destroy(orphan_id, remove_volumes=True)
        except ProviderError as exc:
            log.warning("orphan_destroy_failed", deployment_id=orphan_id, error=str(exc))
    emitter.kick(events)


# ── Host metrics ─────────────────────────────────────────────────────────────


def _read_proc_cpu() -> tuple[int, int] | None:
    try:
        with open("/proc/stat") as f:
            fields = f.readline().split()[1:]
        values = [int(v) for v in fields]
        idle = values[3] + (values[4] if len(values) > 4 else 0)
        return sum(values), idle
    except (OSError, ValueError, IndexError):
        return None


def _read_meminfo() -> tuple[int, int] | None:
    try:
        info: dict[str, int] = {}
        with open("/proc/meminfo") as f:
            for line in f:
                key, _, rest = line.partition(":")
                info[key] = int(rest.strip().split()[0])  # kB
        total_mb = info["MemTotal"] // 1024
        used_mb = (info["MemTotal"] - info.get("MemAvailable", info["MemTotal"])) // 1024
        return total_mb, used_mb
    except (OSError, KeyError, ValueError):
        return None


@celery_app.task(name="app.workers.tasks.sample_host_metrics")
def sample_host_metrics() -> None:
    cpu_percent = 0.0
    first = _read_proc_cpu()
    if first is not None:
        time.sleep(1)
        second = _read_proc_cpu()
        if second is not None:
            total_delta = second[0] - first[0]
            idle_delta = second[1] - first[1]
            if total_delta > 0:
                cpu_percent = round(100.0 * (1 - idle_delta / total_delta), 2)

    mem = _read_meminfo()
    disk = shutil.disk_usage("/")
    try:
        running = get_provider().host_capacity().running_containers
    except ProviderError:
        running = 0

    with session_scope() as db:
        MetricsRepository(db).add(HostMetric(
            cpu_percent=Decimal(str(cpu_percent)),
            memory_used_mb=mem[1] if mem else 0,
            memory_total_mb=mem[0] if mem else 0,
            disk_used_gb=Decimal(disk.used) / (1024**3),
            disk_total_gb=Decimal(disk.total) / (1024**3),
            running_containers=running,
        ))
