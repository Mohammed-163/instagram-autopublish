from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database.client import get_session
from database.models import EngineHealth
from database.repositories.base_repository import BaseRepository


class EngineHealthRepository(BaseRepository[EngineHealth]):
    model = EngineHealth

    def get_by_name(self, engine_name: str) -> Optional[EngineHealth]:
        with get_session() as session:
            stmt = select(EngineHealth).where(EngineHealth.engine_name == engine_name)
            return session.scalars(stmt).first()

    def list_unhealthy(self) -> List[EngineHealth]:
        with get_session() as session:
            stmt = select(EngineHealth).where(EngineHealth.status.in_(["degraded", "down"]))
            return list(session.scalars(stmt).all())

    def report_heartbeat(self, engine_name: str, status: str, **values) -> None:
        """Insert-or-update a single engine's health row by its unique name."""
        with get_session() as session:
            stmt = pg_insert(EngineHealth).values(engine_name=engine_name, status=status, **values)
            update_cols = {"status": stmt.excluded.status, **{k: getattr(stmt.excluded, k) for k in values.keys()}}
            stmt = stmt.on_conflict_do_update(index_elements=[EngineHealth.engine_name], set_=update_cols)
            session.execute(stmt)


engine_health_repository = EngineHealthRepository()
