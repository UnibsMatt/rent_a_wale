"""Test harness: in-memory SQLite, fake Redis, fake DeploymentProvider, and a
TestClient wired through dependency overrides. No Docker, Postgres, or broker needed."""

from __future__ import annotations

import itertools
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.core.db as core_db
from app.core.db import get_db
from app.core.security import hash_password
from app.models import Base, CreditAccount, PricingPlan, User
from app.models.enums import UserRole
from app.providers.base import (
    DeploymentProvider,
    DeploymentSpec,
    HostCapacity,
    ServiceState,
    ServiceStats,
)


# ── SQLite compatibility ──────────────────────────────────────────────────────


@compiles(JSONB, "sqlite")
def _jsonb_sqlite(type_, compiler, **kw):  # noqa: ANN001, ANN003
    return "JSON"


_user_numbers = itertools.count(1)


@event.listens_for(User, "before_insert")
def _fill_user_number(mapper, connection, target) -> None:  # noqa: ANN001
    if target.user_number is None:
        target.user_number = next(_user_numbers)


# ── Fakes ─────────────────────────────────────────────────────────────────────


class FakeRedis:
    """Just enough of redis-py for the denylist and rate limiter."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def exists(self, key: str) -> int:
        return 1 if key in self.store else 0

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value

    def incr(self, key: str) -> int:
        self.store[key] = str(int(self.store.get(key, "0")) + 1)
        return int(self.store[key])

    def expire(self, key: str, ttl: int) -> None:
        pass

    def ping(self) -> bool:
        return True


class FakeProvider(DeploymentProvider):
    """In-memory provider: records lifecycle calls, reports generous capacity."""

    def __init__(self) -> None:
        self.deployments: dict[str, list[ServiceState]] = {}
        self.calls: list[tuple[str, str]] = []

    def provision(self, spec: DeploymentSpec) -> list[ServiceState]:
        self.calls.append(("provision", spec.deployment_id))
        states = [
            ServiceState(
                name=s.name, container_id=f"cid-{s.name}",
                container_name=f"{spec.owner_namespace}-{spec.slug}-{s.name}",
                status="running",
            )
            for s in spec.services
        ]
        self.deployments[spec.deployment_id] = states
        return states

    def _all(self, deployment_id: str, status: str) -> list[ServiceState]:
        states = self.deployments.get(deployment_id, [])
        for s in states:
            s.status = status
        return states

    def start(self, deployment_id: str) -> list[ServiceState]:
        self.calls.append(("start", deployment_id))
        return self._all(deployment_id, "running")

    def stop(self, deployment_id: str, timeout_s: int = 10) -> list[ServiceState]:
        self.calls.append(("stop", deployment_id))
        return self._all(deployment_id, "exited")

    def restart(self, deployment_id: str, timeout_s: int = 10) -> list[ServiceState]:
        self.calls.append(("restart", deployment_id))
        return self._all(deployment_id, "running")

    def pause(self, deployment_id: str) -> list[ServiceState]:
        self.calls.append(("pause", deployment_id))
        return self._all(deployment_id, "paused")

    def resume(self, deployment_id: str) -> list[ServiceState]:
        self.calls.append(("resume", deployment_id))
        return self._all(deployment_id, "running")

    def destroy(self, deployment_id: str, *, remove_volumes: bool = True) -> None:
        self.calls.append(("destroy", deployment_id))
        self.deployments.pop(deployment_id, None)

    def status(self, deployment_id: str) -> list[ServiceState]:
        return self.deployments.get(deployment_id, [])

    def stats(self, deployment_id: str) -> list[ServiceStats]:
        return [
            ServiceStats(
                name=s.name, cpu_percent=1.0, memory_used_mb=10.0, memory_limit_mb=512.0,
                network_rx_mb=0.1, network_tx_mb=0.1, status=s.status,
                restart_count=0, healthy=True,
            )
            for s in self.deployments.get(deployment_id, [])
        ]

    def logs(self, deployment_id: str, service_name=None, *, tail=200, follow=False):
        yield "[app] hello from fake provider\n"

    def host_capacity(self) -> HostCapacity:
        return HostCapacity(
            total_cpu_cores=Decimal("64"), total_memory_mb=262_144,
            total_disk_gb=Decimal("2000"), used_disk_gb=Decimal("100"),
            cpu_percent=5.0, memory_used_mb=1024, running_containers=0,
        )

    def list_managed_deployment_ids(self) -> set[str]:
        return set(self.deployments)


# ── Engine / session ──────────────────────────────────────────────────────────


@pytest.fixture()
def engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def SessionFactory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@pytest.fixture()
def db(SessionFactory) -> Session:
    session = SessionFactory()
    yield session
    session.close()


# ── Global patches ────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch) -> FakeRedis:
    fake = FakeRedis()
    monkeypatch.setattr("app.core.security.get_redis", lambda: fake)
    monkeypatch.setattr("app.core.rate_limit.get_redis", lambda: fake)
    return fake


@pytest.fixture(autouse=True)
def fake_provider(monkeypatch) -> FakeProvider:
    provider = FakeProvider()
    monkeypatch.setattr("app.services.host_service.get_provider", lambda: provider)
    monkeypatch.setattr("app.services.deployment_service.get_provider", lambda: provider)
    monkeypatch.setattr("app.workers.tasks.get_provider", lambda: provider)
    return provider


@pytest.fixture(autouse=True)
def captured_tasks(monkeypatch) -> list:
    """Neutralize Celery + event kicks; record what would have been enqueued."""
    captured: list[tuple[str, tuple]] = []
    monkeypatch.setattr("app.events.emitter.kick", lambda ids: captured.append(("kick", tuple(ids))))
    monkeypatch.setattr(
        "app.services.deployment_service._enqueue",
        lambda task, *args: captured.append((task, args)),
    )
    return captured


@pytest.fixture(autouse=True)
def patch_session_scope(monkeypatch, SessionFactory):
    """Worker tasks use session_scope() → point it at the test database."""
    monkeypatch.setattr(core_db, "SessionLocal", SessionFactory)
    return SessionFactory


# ── App / client ──────────────────────────────────────────────────────────────


@pytest.fixture()
def client(SessionFactory):
    from app.main import app

    def override_get_db():
        session = SessionFactory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ── Data fixtures ─────────────────────────────────────────────────────────────


DEFAULT_SNAPSHOT_PRICES = dict(
    base_cost_per_hour=Decimal("0"),
    cpu_cost_per_core_hour=Decimal("1"),
    memory_cost_per_gb_hour=Decimal("1"),
    storage_cost_per_gb_hour=Decimal("0.05"),
    service_cost_per_hour=Decimal("0.25"),
)


@pytest.fixture()
def pricing_plan(db) -> PricingPlan:
    plan = PricingPlan(name="default", is_active=True, **DEFAULT_SNAPSHOT_PRICES)
    db.add(plan)
    db.commit()
    return plan


def make_user(
    db: Session, email: str, *, role: str = UserRole.USER,
    balance: Decimal = Decimal("0"), password: str = "s3cret-password",
) -> User:
    user = User(email=email, hashed_password=hash_password(password), role=role)
    db.add(user)
    db.flush()
    db.add(CreditAccount(user_id=user.id, balance=balance))
    db.commit()
    return user


@pytest.fixture()
def user(db) -> User:
    return make_user(db, "user@example.com", balance=Decimal("100"))


@pytest.fixture()
def admin(db) -> User:
    return make_user(db, "admin@example.com", role=UserRole.ADMIN)


def login(client: TestClient, email: str, password: str = "s3cret-password") -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def user_headers(client, user) -> dict[str, str]:
    return login(client, user.email)


@pytest.fixture()
def admin_headers(client, admin) -> dict[str, str]:
    return login(client, admin.email)
