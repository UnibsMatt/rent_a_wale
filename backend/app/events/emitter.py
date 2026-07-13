"""Transactional-outbox event emitter.

`emit()` writes the event row inside the caller's transaction — a state change and its
event commit or roll back together. After commit the caller invokes `kick()` to push
the event ids to Celery by task *name* (no import of worker modules, no cycles).
A beat task relays any event whose kick was lost (process crash between commit and
send), so delivery is at-least-once; consumers are idempotent.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import DeploymentEvent
from app.models.enums import DeploymentEventType

log = get_logger("app")

HANDLE_EVENT_TASK = "app.workers.tasks.handle_event"


def emit(
    db: Session,
    deployment_id: uuid.UUID,
    event_type: DeploymentEventType,
    payload: dict | None = None,
) -> DeploymentEvent:
    event = DeploymentEvent(
        deployment_id=deployment_id,
        event_type=event_type,
        payload=payload or {},
        dispatched=False,
    )
    db.add(event)
    db.flush()
    return event


def kick(event_ids: list[uuid.UUID]) -> None:
    """Best-effort immediate dispatch — call only after the transaction committed."""
    from app.workers.celery_app import celery_app  # local import: keep web free of worker deps

    for event_id in event_ids:
        try:
            celery_app.send_task(HANDLE_EVENT_TASK, args=[str(event_id)])
        except Exception as exc:  # broker down: the outbox relay will pick it up
            log.warning("event_kick_failed", event_id=str(event_id), error=str(exc))
