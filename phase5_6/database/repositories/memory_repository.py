from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database.client import get_session
from database.models import MemoryEntry
from database.repositories.base_repository import BaseRepository


class MemoryRepository(BaseRepository[MemoryEntry]):
    model = MemoryEntry

    def get_by_key(self, memory_key: str) -> Optional[MemoryEntry]:
        with get_session() as session:
            stmt = select(MemoryEntry).where(MemoryEntry.memory_key == memory_key)
            return session.scalars(stmt).first()

    def list_by_category(self, category: str) -> List[MemoryEntry]:
        with get_session() as session:
            stmt = select(MemoryEntry).where(MemoryEntry.category == category)
            return list(session.scalars(stmt).all())

    def remember(self, memory_key: str, memory_value: dict, **values) -> None:
        """Insert-or-update a memory entry by its unique key."""
        with get_session() as session:
            stmt = pg_insert(MemoryEntry).values(memory_key=memory_key, memory_value=memory_value, **values)
            update_cols = {"memory_value": stmt.excluded.memory_value, **{k: getattr(stmt.excluded, k) for k in values.keys()}}
            stmt = stmt.on_conflict_do_update(index_elements=[MemoryEntry.memory_key], set_=update_cols)
            session.execute(stmt)


memory_repository = MemoryRepository()
