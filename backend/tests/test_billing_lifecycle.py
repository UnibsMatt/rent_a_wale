"""Billing tick: per-period metering, idempotency, exhaustion → automatic stop.
Exercises the real worker function against the test database."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.models import CreditTransaction, Deployment, UsageRecord
from app.models.enums import DeploymentEventType, DeploymentStatus
from app.workers.tasks import _bill_deployment
from tests.conftest import make_user

SNAPSHOT = {
    "plan_id": str(uuid.uuid4()),
    "plan_name": "default",
    "base_cost_per_hour": "0",
    "cpu_cost_per_core_hour": "1",
    "memory_cost_per_gb_hour": "1",
    "storage_cost_per_gb_hour": "0.05",
    "service_cost_per_hour": "0.25",
}


@pytest.fixture()
def running_deployment(db):
    """1 CPU + 2 GB → 3 credits/hour → 0.05 credits/minute."""
    owner = make_user(db, "billed@example.com", balance=Decimal("0.12"))
    deployment = Deployment(
        owner_id=owner.id,
        name="metered",
        slug="metered-abcd",
        kind="image",
        status=DeploymentStatus.RUNNING,
        cpu_cores=Decimal("1"),
        memory_mb=2048,
        storage_gb=0,
        spec={"storage_gb": 0, "services": []},
        price_snapshot=SNAPSHOT,
        estimated_hourly_cost=Decimal("3"),
        started_at=datetime.now(UTC),
    )
    db.add(deployment)
    db.commit()
    return deployment


def _tick(deployment_id, start: datetime) -> None:
    _bill_deployment(deployment_id, start, start + timedelta(seconds=60), 60)


def test_tick_charges_one_minute(db, running_deployment, captured_tasks):
    start = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)
    _tick(running_deployment.id, start)

    records = db.query(UsageRecord).filter_by(deployment_id=running_deployment.id).all()
    assert len(records) == 1
    assert records[0].credits_charged == Decimal("0.05")

    tx = db.query(CreditTransaction).filter_by(deployment_id=running_deployment.id).one()
    assert tx.amount == Decimal("-0.05")
    assert tx.balance_after == Decimal("0.07")


def test_tick_is_idempotent_per_period(db, running_deployment):
    start = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)
    _tick(running_deployment.id, start)
    _tick(running_deployment.id, start)  # replayed delivery

    records = db.query(UsageRecord).filter_by(deployment_id=running_deployment.id).all()
    assert len(records) == 1  # unique (deployment_id, period_start) honored


def test_distinct_periods_both_bill(db, running_deployment):
    base = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)
    _tick(running_deployment.id, base)
    _tick(running_deployment.id, base + timedelta(minutes=1))

    records = db.query(UsageRecord).filter_by(deployment_id=running_deployment.id).all()
    assert len(records) == 2


def test_exhaustion_charges_remainder_and_stops(db, running_deployment, monkeypatch):
    stop_calls: list = []
    monkeypatch.setattr(
        "app.workers.tasks.celery_app.send_task",
        lambda name, args=None, kwargs=None: stop_calls.append((name, args, kwargs)),
    )

    base = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)
    # Balance 0.12 → minute 1 leaves 0.07, minute 2 leaves 0.02 (< 0.05 → exhausted).
    _tick(running_deployment.id, base)
    _tick(running_deployment.id, base + timedelta(minutes=1))

    assert stop_calls, "exhaustion must enqueue the stop task"
    name, args, kwargs = stop_calls[0]
    assert name.endswith("stop_deployment")
    assert kwargs == {"reason": "credit_exhausted"}

    # Third tick: only 0.02 left → partial charge down to exactly zero, never negative.
    _tick(running_deployment.id, base + timedelta(minutes=2))
    from app.repositories.users import CreditAccountRepository

    account = CreditAccountRepository(db).get_by_user(running_deployment.owner_id)
    db.refresh(account)
    assert account.balance == Decimal("0")

    from app.models import DeploymentEvent

    events = (
        db.query(DeploymentEvent).filter_by(deployment_id=running_deployment.id).all()
    )
    assert any(e.event_type == DeploymentEventType.CREDIT_EXHAUSTED for e in events)


def test_stopped_deployment_not_billed(db, running_deployment):
    running_deployment.status = DeploymentStatus.STOPPED
    db.commit()
    _tick(running_deployment.id, datetime(2026, 7, 13, 12, 0, tzinfo=UTC))
    assert db.query(UsageRecord).count() == 0


def test_stop_task_closes_deployment_with_reason(db, running_deployment, fake_provider):
    from app.workers.tasks import stop_deployment

    fake_provider.deployments[str(running_deployment.id)] = []
    stop_deployment(str(running_deployment.id), reason="credit_exhausted")

    db.refresh(running_deployment)
    assert running_deployment.status == DeploymentStatus.CREDIT_EXHAUSTED
    assert running_deployment.stopped_at is not None
    assert ("stop", str(running_deployment.id)) in fake_provider.calls
