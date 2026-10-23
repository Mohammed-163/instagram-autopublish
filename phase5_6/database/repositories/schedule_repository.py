from __future__ import annotations

import uuid
from datetime import datetime
from typing import List

from sqlalchemy import select, text

from database.client import get_session
from database.models import PublishingSchedule
from database.repositories.base_repository import BaseRepository


class ScheduleRepository(BaseRepository[PublishingSchedule]):
    model = PublishingSchedule

    def list_due(self, limit: int = 50) -> List[PublishingSchedule]:
        """Pending schedule entries whose time has come, highest priority first."""
        with get_session() as session:
            stmt = (
                select(PublishingSchedule)
                .where(PublishingSchedule.status == "pending")
                .where(PublishingSchedule.scheduled_at <= datetime.utcnow())
                .order_by(PublishingSchedule.priority.desc(), PublishingSchedule.scheduled_at.asc())
                .limit(limit)
            )
            return list(session.scalars(stmt).all())

    def list_due_posts_view(self) -> list:
        """Reads the v_due_posts view (views.sql) for a ready-to-publish
        list joined with post text in one round trip."""
        with get_session() as session:
            rows = session.execute(text("SELECT * FROM v_due_posts")).mappings().all()
            return [dict(row) for row in rows]

    def lock(self, schedule_id: uuid.UUID) -> None:
        self.update(schedule_id, status="locked")

    def mark_done(self, schedule_id: uuid.UUID) -> None:
        self.update(schedule_id, status="done")

    def cancel(self, schedule_id: uuid.UUID) -> None:
        self.update(schedule_id, status="cancelled")


schedule_repository = ScheduleRepository()
