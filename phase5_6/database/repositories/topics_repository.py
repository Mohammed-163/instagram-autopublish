from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select, text

from database.client import get_session
from database.models import Topic
from database.repositories.base_repository import BaseRepository


class TopicsRepository(BaseRepository[Topic]):
    model = Topic

    def get_by_slug(self, slug: str) -> Optional[Topic]:
        with get_session() as session:
            return session.scalars(select(Topic).where(Topic.slug == slug)).first()

    def list_ordered_by_weight(self) -> List[Topic]:
        with get_session() as session:
            stmt = select(Topic).order_by(Topic.current_weight.desc())
            return list(session.scalars(stmt).all())

    def refresh_stats(self, topic_id: uuid.UUID) -> None:
        """Recomputes posts_count/avg_reach/avg_saves/avg_performance from
        the metrics table, via the refresh_topic_stats() SQL function
        (functions.sql). Call after writing a new '24h' metrics snapshot."""
        with get_session() as session:
            session.execute(text("SELECT refresh_topic_stats(:topic_id)"), {"topic_id": str(topic_id)})

    def set_weight(self, topic_id: uuid.UUID, new_weight) -> Optional[Topic]:
        return self.update(topic_id, current_weight=new_weight)


topics_repository = TopicsRepository()
