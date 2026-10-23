from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database.client import get_session
from database.models import Metric
from database.repositories.base_repository import BaseRepository


class MetricsRepository(BaseRepository[Metric]):
    model = Metric

    def list_for_post(self, post_id: uuid.UUID) -> List[Metric]:
        with get_session() as session:
            stmt = select(Metric).where(Metric.post_id == post_id).order_by(Metric.captured_at.desc())
            return list(session.scalars(stmt).all())

    def get_snapshot(self, post_id: uuid.UUID, snapshot_period: str) -> Optional[Metric]:
        with get_session() as session:
            stmt = select(Metric).where(
                Metric.post_id == post_id, Metric.snapshot_period == snapshot_period
            )
            return session.scalars(stmt).first()

    def upsert_snapshot(self, post_id: uuid.UUID, snapshot_period: str, captured_at: datetime, **values) -> None:
        """Insert a metrics snapshot, or overwrite the existing one for the
        same (post_id, snapshot_period) — matches the UNIQUE constraint in
        schema.sql so re-fetching insights for the same window is idempotent."""
        with get_session() as session:
            stmt = pg_insert(Metric).values(
                post_id=post_id, snapshot_period=snapshot_period, captured_at=captured_at, **values
            )
            update_cols = {k: getattr(stmt.excluded, k) for k in list(values.keys()) + ["captured_at"]}
            stmt = stmt.on_conflict_do_update(
                index_elements=[Metric.post_id, Metric.snapshot_period],
                set_=update_cols,
            )
            session.execute(stmt)


metrics_repository = MetricsRepository()
