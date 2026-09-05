from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from sqlalchemy import select

from database.client import get_session
from database.models import Notification
from database.repositories.base_repository import BaseRepository


class NotificationsRepository(BaseRepository[Notification]):
    model = Notification

    def list_pending(self) -> List[Notification]:
        with get_session() as session:
            stmt = select(Notification).where(Notification.status == "pending")
            return list(session.scalars(stmt).all())

    def mark_sent(self, notification_id) -> None:
        self.update(notification_id, status="sent", sent_at=datetime.now(timezone.utc))

    def mark_failed(self, notification_id) -> None:
        self.update(notification_id, status="failed")


notifications_repository = NotificationsRepository()
