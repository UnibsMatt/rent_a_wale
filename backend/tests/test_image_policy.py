"""Image allow/block pattern semantics."""

from __future__ import annotations

import pytest

from app.core.exceptions import ValidationFailedError
from app.models import ImageRule
from app.models.enums import ImageRuleMode
from app.services.image_policy import ImagePolicyService, normalize_image


def test_normalize_strips_registry_prefixes():
    assert normalize_image("docker.io/library/nginx:1.27") == "nginx:1.27"
    assert normalize_image("docker.io/bitnami/redis") == "bitnami/redis"
    assert normalize_image("nginx") == "nginx"


def _service_with_rules(db, rules: list[tuple[str, str]]) -> ImagePolicyService:
    for pattern, mode in rules:
        db.add(ImageRule(pattern=pattern, mode=mode))
    db.commit()
    return ImagePolicyService(db)


def test_no_rules_allows_everything(db):
    _service_with_rules(db, []).check("anything/at-all:v9")


def test_allowlist_mode_blocks_unlisted(db):
    service = _service_with_rules(db, [("nginx", ImageRuleMode.ALLOW)])
    service.check("nginx:1.27")
    service.check("nginx")
    with pytest.raises(ValidationFailedError):
        service.check("redis:7")


def test_block_beats_allow(db):
    service = _service_with_rules(
        db, [("nginx", ImageRuleMode.ALLOW), ("nginx:evil", ImageRuleMode.BLOCK)]
    )
    service.check("nginx:1.27")
    with pytest.raises(ValidationFailedError):
        service.check("nginx:evil")


def test_namespace_wildcard(db):
    service = _service_with_rules(db, [("bitnami/*", ImageRuleMode.ALLOW)])
    service.check("bitnami/redis:7")
    service.check("docker.io/bitnami/postgresql")
    with pytest.raises(ValidationFailedError):
        service.check("nginx")


def test_exact_tag_rule_only_matches_that_tag(db):
    service = _service_with_rules(db, [("python:3.12-slim", ImageRuleMode.ALLOW)])
    service.check("python:3.12-slim")
    with pytest.raises(ValidationFailedError):
        service.check("python:2.7")
