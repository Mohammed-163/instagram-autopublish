from __future__ import annotations

import uuid
from typing import List

from sqlalchemy import select

from database.client import get_session
from database.models import Design
from database.repositories.base_repository import BaseRepository


class DesignsRepository(BaseRepository[Design]):
    model = Design

    def list_for_post(self, post_id: uuid.UUID) -> List[Design]:
        with get_session() as session:
            stmt = select(Design).where(Design.post_id == post_id).order_by(Design.created_at.desc())
            return list(session.scalars(stmt).all())


designs_repository = DesignsRepository()
