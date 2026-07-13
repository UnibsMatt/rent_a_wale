from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.models import AuditLog, ComposeTemplate, HostMetric, ImageRule
from app.models.enums import TemplateStatus
from app.repositories.base import Repository


class ImageRuleRepository(Repository):
    def list_all(self) -> list[ImageRule]:
        return list(self.db.scalars(select(ImageRule)).all())

    def add(self, rule: ImageRule) -> ImageRule:
        self.db.add(rule)
        self.db.flush()
        return rule

    def get(self, rule_id: uuid.UUID) -> ImageRule | None:
        return self.db.get(ImageRule, rule_id)

    def delete(self, rule: ImageRule) -> None:
        self.db.delete(rule)


class TemplateRepository(Repository):
    def add(self, template: ComposeTemplate) -> ComposeTemplate:
        self.db.add(template)
        self.db.flush()
        return template

    def get(self, template_id: uuid.UUID) -> ComposeTemplate | None:
        return self.db.get(ComposeTemplate, template_id)

    def list_approved(self) -> list[ComposeTemplate]:
        return list(
            self.db.scalars(
                select(ComposeTemplate).where(ComposeTemplate.status == TemplateStatus.APPROVED)
            ).all()
        )

    def list_all(self) -> list[ComposeTemplate]:
        return list(
            self.db.scalars(
                select(ComposeTemplate).order_by(ComposeTemplate.created_at.desc())
            ).all()
        )


class AuditRepository(Repository):
    def add(self, entry: AuditLog) -> AuditLog:
        self.db.add(entry)
        return entry

    def list_paged(self, *, page: int, page_size: int) -> tuple[list[AuditLog], int]:
        total = self.db.scalar(select(func.count()).select_from(AuditLog)) or 0
        rows = self.db.scalars(
            select(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(rows), total


class MetricsRepository(Repository):
    def add(self, metric: HostMetric) -> HostMetric:
        self.db.add(metric)
        return metric

    def latest(self) -> HostMetric | None:
        return self.db.scalar(
            select(HostMetric).order_by(HostMetric.sampled_at.desc()).limit(1)
        )
