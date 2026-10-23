from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select

from database.client import get_session
from database.models import Post
from database.repositories.base_repository import BaseRepository


class PostsRepository(BaseRepository[Post]):
    model = Post

    def list_by_status(self, status: str, limit: int = 200) -> List[Post]:
        with get_session() as session:
            stmt = select(Post).where(Post.status == status).limit(limit)
            return list(session.scalars(stmt).all())

    def list_scheduled_before(self, cutoff: datetime, limit: int = 200) -> List[Post]:
        with get_session() as session:
            stmt = (
                select(Post)
                .where(Post.status.in_(("ready", "scheduled")))
                .where(Post.scheduled_at.is_not(None))
                .where(Post.scheduled_at <= cutoff)
                .order_by(Post.scheduled_at.asc())
                .limit(limit)
            )
            return list(session.scalars(stmt).all())

    def get_by_instagram_media_id(self, media_id: str) -> Optional[Post]:
        with get_session() as session:
            return session.scalars(
                select(Post).where(Post.instagram_media_id == media_id)
            ).first()

    def mark_publishing(self, post_id: uuid.UUID) -> Optional[Post]:
        return self.update(post_id, status="publishing")

    def mark_published(
        self, post_id: uuid.UUID, instagram_media_id: str, instagram_permalink: Optional[str] = None
    ) -> Optional[Post]:
        return self.update(
            post_id,
            status="published",
            published_at=datetime.utcnow(),
            instagram_media_id=instagram_media_id,
            instagram_permalink=instagram_permalink,
        )

    def mark_failed(self, post_id: uuid.UUID) -> Optional[Post]:
        return self.update(post_id, status="failed")

    def mark_cleaned(self, post_id: uuid.UUID) -> Optional[Post]:
        return self.update(post_id, status="cleaned")


posts_repository = PostsRepository()
