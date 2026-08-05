from __future__ import annotations

import uuid
from typing import List

from sqlalchemy import select

from database.client import get_session
from database.models import Media
from database.repositories.base_repository import BaseRepository


class MediaRepository(BaseRepository[Media]):
    model = Media

    def list_for_post(self, post_id: uuid.UUID) -> List[Media]:
        with get_session() as session:
            stmt = select(Media).where(Media.post_id == post_id).order_by(Media.created_at.desc())
            return list(session.scalars(stmt).all())


media_repository = MediaRepository()
