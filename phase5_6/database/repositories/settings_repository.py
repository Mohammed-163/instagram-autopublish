from __future__ import annotations

from typing import Any, List, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database.client import get_session
from database.models import SystemSetting


class SettingsRepository:
    """system_settings is keyed by a TEXT primary key, not a UUID, so it
    doesn't fit BaseRepository's get_by_id(uuid) signature — it gets its
    own small repository instead."""

    def get(self, key: str) -> Optional[Any]:
        with get_session() as session:
            row = session.get(SystemSetting, key)
            return row.value if row else None

    def list_all(self) -> List[SystemSetting]:
        with get_session() as session:
            return list(session.scalars(select(SystemSetting)).all())

    def set(self, key: str, value: Any, description: Optional[str] = None) -> None:
        with get_session() as session:
            stmt = pg_insert(SystemSetting).values(key=key, value=value, description=description)
            stmt = stmt.on_conflict_do_update(
                index_elements=[SystemSetting.key],
                set_={"value": stmt.excluded.value, "description": stmt.excluded.description},
            )
            session.execute(stmt)

    def delete(self, key: str) -> bool:
        with get_session() as session:
            row = session.get(SystemSetting, key)
            if row is None:
                return False
            session.delete(row)
            return True


settings_repository = SettingsRepository()
