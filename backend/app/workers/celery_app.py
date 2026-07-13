from __future__ import annotations

from celery import Celery
from celery.signals import setup_logging as celery_setup_logging

from app.core.config import settings
from app.core.logging import configure_logging

celery_app = Celery(
    "rentawhale",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    task_routes={
        # Billing must never starve behind slow provisioning work.
        "app.workers.tasks.billing_tick": {"queue": "billing"},
        "app.workers.tasks.handle_event": {"queue": "billing"},
        "app.workers.tasks.relay_outbox": {"queue": "billing"},
    },
    beat_schedule={
        "billing-tick": {
            "task": "app.workers.tasks.billing_tick",
            "schedule": float(settings.billing_tick_seconds),
        },
        "reconcile-deployments": {
            "task": "app.workers.tasks.reconcile_deployments",
            "schedule": 120.0,
        },
        "sample-host-metrics": {
            "task": "app.workers.tasks.sample_host_metrics",
            "schedule": 30.0,
        },
        "relay-outbox": {
            "task": "app.workers.tasks.relay_outbox",
            "schedule": 60.0,
        },
    },
)


@celery_setup_logging.connect
def _setup_logging(**_kwargs) -> None:
    configure_logging()
