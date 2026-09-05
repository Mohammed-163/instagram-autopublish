from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select

from database.client import get_session
from database.models import PublishingHistory
from database.repositories.base_repository import BaseRepository


class HistoryRepository(BaseRepository[PublishingHistory]):
    model = PublishingHistory

    def list_for_post(self, post_id: uuid.UUID) -> List[PublishingHistory]:
        with get_session() as session:
            stmt = (
                select(PublishingHistory)
                .where(PublishingHistory.post_id == post_id)
                .order_by(PublishingHistory.started_at.desc())
            )
            return list(session.scalars(stmt).all())

    def record_attempt(
        self,
        post_id: uuid.UUID,
        started_at: datetime,
        ended_at: Optional[datetime],
        attempt_number: int,
        result: str,
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> PublishingHistory:
        return self.create(
            post_id=post_id,
            started_at=started_at,
            ended_at=ended_at,
            attempt_number=attempt_number,
            result=result,
            error_message=error_message,
            duration_ms=duration_ms,
        )


history_repository = HistoryRepository()
