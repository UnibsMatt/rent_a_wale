from __future__ import annotations

import uuid

from sqlalchemy import select, update

from app.models import RefreshToken, UserSession
from app.repositories.base import Repository


class SessionRepository(Repository):
    def add(self, session: UserSession) -> UserSession:
        self.db.add(session)
        self.db.flush()
        return session

    def get(self, session_id: uuid.UUID) -> UserSession | None:
        return self.db.get(UserSession, session_id)

    def list_for_user(self, user_id: uuid.UUID) -> list[UserSession]:
        return list(
            self.db.scalars(
                select(UserSession)
                .where(UserSession.user_id == user_id, UserSession.revoked.is_(False))
                .order_by(UserSession.created_at.desc())
            ).all()
        )

    def revoke(self, session_id: uuid.UUID) -> None:
        self.db.execute(
            update(UserSession).where(UserSession.id == session_id).values(revoked=True)
        )

    def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        self.db.execute(
            update(UserSession).where(UserSession.user_id == user_id).values(revoked=True)
        )


class RefreshTokenRepository(Repository):
    def add(self, token: RefreshToken) -> RefreshToken:
        self.db.add(token)
        self.db.flush()
        return token

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return self.db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))

    def revoke_session_family(self, session_id: uuid.UUID) -> None:
        self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.session_id == session_id)
            .values(revoked=True)
        )

    def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        self.db.execute(
            update(RefreshToken).where(RefreshToken.user_id == user_id).values(revoked=True)
        )
