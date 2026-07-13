from __future__ import annotations

from datetime import UTC, datetime


def ensure_utc(dt: datetime) -> datetime:
    """Normalize possibly-naive timestamps (SQLite test backend) to aware UTC.
    Postgres columns are timestamptz, so this is a no-op in production."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
