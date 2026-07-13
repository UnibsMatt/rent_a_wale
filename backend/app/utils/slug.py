from __future__ import annotations

import re
import secrets

_INVALID = re.compile(r"[^a-z0-9-]+")


def slugify(name: str, *, max_len: int = 32) -> str:
    slug = _INVALID.sub("-", name.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)[:max_len].strip("-")
    return slug or "app"


def random_suffix(n: int = 4) -> str:
    return secrets.token_hex((n + 1) // 2)[:n]
