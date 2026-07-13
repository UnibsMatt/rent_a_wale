from __future__ import annotations

from sqlalchemy.orm import Session


class Repository:
    """Repositories own persistence only — no business rules, no commits.
    Transaction boundaries belong to the service layer."""

    def __init__(self, db: Session) -> None:
        self.db = db
