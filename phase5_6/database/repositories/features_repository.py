from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database.client import get_session
from database.models import Feature
from database.repositories.base_repository import BaseRepository


class FeaturesRepository(BaseRepository[Feature]):
    model = Feature

    def list_for_post(self, post_id: uuid.UUID) -> List[Feature]:
        with get_session() as session:
            stmt = select(Feature).where(Feature.post_id == post_id)
            return list(session.scalars(stmt).all())

    def get_feature(self, post_id: uuid.UUID, feature_key: str) -> Optional[Feature]:
        with get_session() as session:
            stmt = select(Feature).where(Feature.post_id == post_id, Feature.feature_key == feature_key)
            return session.scalars(stmt).first()

    def upsert_feature(self, post_id: uuid.UUID, feature_key: str, **values) -> None:
        """Insert or overwrite a single (post_id, feature_key) feature —
        matches the UNIQUE constraint in the migration, so re-extraction is
        idempotent."""
        with get_session() as session:
            stmt = pg_insert(Feature).values(post_id=post_id, feature_key=feature_key, **values)
            update_cols = {k: getattr(stmt.excluded, k) for k in values.keys()}
            stmt = stmt.on_conflict_do_update(
                index_elements=[Feature.post_id, Feature.feature_key],
                set_=update_cols,
            )
            session.execute(stmt)


features_repository = FeaturesRepository()
