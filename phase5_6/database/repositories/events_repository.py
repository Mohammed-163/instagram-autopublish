from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select

from database.client import get_session
from database.models import EventLog
from database.repositories.base_repository import BaseRepository


class EventsRepository(BaseRepository[EventLog]):
    model = EventLog

    def log(self, event_type: str, source: str, payload: Optional[dict] = None) -> EventLog:
        """Appends one event. This is the single write path future
        Event-Driven engines should call instead of writing to event_logs
        directly."""
        return self.create(event_type=event_type, source=source, payload=payload)

    def list_by_type(self, event_type: str, limit: int = 200) -> List[EventLog]:
        with get_session() as session:
            stmt = select(EventLog).where(EventLog.event_type == event_type).order_by(
                EventLog.occurred_at.desc()
            ).limit(limit)
            return list(session.scalars(stmt).all())


events_repository = EventsRepository()
