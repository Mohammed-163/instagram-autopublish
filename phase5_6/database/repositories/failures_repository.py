from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from sqlalchemy import select

from database.client import get_session
from database.models import Failure
from database.repositories.base_repository import BaseRepository


class FailuresRepository(BaseRepository[Failure]):
    model = Failure

    def list_unresolved(self) -> List[Failure]:
        with get_session() as session:
            stmt = select(Failure).where(Failure.resolved.is_(False))
            return list(session.scalars(stmt).all())

    def resolve(self, failure_id) -> None:
        self.update(failure_id, resolved=True, resolved_at=datetime.now(timezone.utc))


failures_repository = FailuresRepository()
