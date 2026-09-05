from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database.client import get_session
from database.models import Score
from database.repositories.base_repository import BaseRepository


class ScoresRepository(BaseRepository[Score]):
    model = Score

    def list_for_post(self, post_id: uuid.UUID) -> List[Score]:
        with get_session() as session:
            stmt = select(Score).where(Score.post_id == post_id)
            return list(session.scalars(stmt).all())

    def get_score(self, post_id: uuid.UUID, score_type: str, method_version: Optional[str] = None) -> Optional[Score]:
        with get_session() as session:
            stmt = select(Score).where(
                Score.post_id == post_id,
                Score.score_type == score_type,
                Score.method_version == method_version,
            )
            return session.scalars(stmt).first()

    def upsert_score(self, post_id: uuid.UUID, score_type: str, score_value, method_version: Optional[str] = None, **values) -> None:
        with get_session() as session:
            stmt = pg_insert(Score).values(
                post_id=post_id, score_type=score_type, score_value=score_value,
                method_version=method_version, **values,
            )
            update_cols = {"score_value": stmt.excluded.score_value, **{k: getattr(stmt.excluded, k) for k in values.keys()}}
            stmt = stmt.on_conflict_do_update(
                index_elements=[Score.post_id, Score.score_type, Score.method_version],
                set_=update_cols,
            )
            session.execute(stmt)


scores_repository = ScoresRepository()
