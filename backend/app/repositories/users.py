from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.models import CreditAccount, User
from app.repositories.base import Repository


class UserRepository(Repository):
    def get(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email.lower()))

    def get_by_verification_token(self, token_hash: str) -> User | None:
        return self.db.scalar(select(User).where(User.email_verification_token == token_hash))

    def get_by_reset_token(self, token_hash: str) -> User | None:
        return self.db.scalar(select(User).where(User.password_reset_token == token_hash))

    def add(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user

    def list_paged(self, *, page: int, page_size: int) -> tuple[list[User], int]:
        total = self.db.scalar(select(func.count()).select_from(User)) or 0
        rows = (
            self.db.scalars(
                select(User)
                .order_by(User.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return list(rows), total


class CreditAccountRepository(Repository):
    def get_by_user(self, user_id: uuid.UUID) -> CreditAccount | None:
        return self.db.scalar(select(CreditAccount).where(CreditAccount.user_id == user_id))

    def get_by_user_for_update(self, user_id: uuid.UUID) -> CreditAccount | None:
        return self.db.scalar(
            select(CreditAccount).where(CreditAccount.user_id == user_id).with_for_update()
        )

    def add(self, account: CreditAccount) -> CreditAccount:
        self.db.add(account)
        self.db.flush()
        return account
