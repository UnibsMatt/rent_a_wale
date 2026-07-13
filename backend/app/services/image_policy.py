"""Image allowlist/blocklist policy.

Rule patterns:
  "nginx"          → any tag of nginx
  "nginx:1.27"     → exactly that tag
  "bitnami/*"      → any image in the bitnami namespace
Block rules always beat allow rules. If at least one allow rule exists the platform is
in allowlist mode: images must match an allow rule.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import ValidationFailedError
from app.models.enums import ImageRuleMode
from app.repositories.governance import ImageRuleRepository


def normalize_image(image: str) -> str:
    """docker.io/library/nginx:1.27 → nginx:1.27 ; docker.io/user/app → user/app"""
    ref = image.strip()
    for prefix in ("docker.io/library/", "docker.io/", "library/"):
        if ref.startswith(prefix):
            ref = ref[len(prefix):]
            break
    return ref


def _matches(pattern: str, image: str) -> bool:
    repo = image.partition("@")[0]
    repo_no_tag = repo.rpartition(":")[0] if ":" in repo.split("/")[-1] else repo
    if pattern.endswith("/*"):
        return repo_no_tag.startswith(pattern[:-1]) or repo_no_tag == pattern[:-2]
    if ":" in pattern.split("/")[-1]:
        return repo == pattern
    return repo_no_tag == pattern


class ImagePolicyService:
    def __init__(self, db: Session) -> None:
        self.repo = ImageRuleRepository(db)

    def check(self, image: str) -> None:
        """Raise ValidationFailedError if the image is not permitted."""
        normalized = normalize_image(image)
        rules = self.repo.list_all()
        blocks = [r for r in rules if r.mode == ImageRuleMode.BLOCK]
        allows = [r for r in rules if r.mode == ImageRuleMode.ALLOW]

        for rule in blocks:
            if _matches(rule.pattern, normalized):
                raise ValidationFailedError(
                    f"Image {image!r} is blocked by platform policy"
                    + (f": {rule.reason}" if rule.reason else "")
                )
        if allows and not any(_matches(rule.pattern, normalized) for rule in allows):
            raise ValidationFailedError(
                f"Image {image!r} is not on the platform allowlist. "
                "Ask an administrator to allow it."
            )

    def check_many(self, images: list[str]) -> None:
        for image in images:
            self.check(image)
