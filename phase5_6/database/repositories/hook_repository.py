from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select

from database.client import get_session
from database.models import HookPattern, HookStatistic
from database.repositories.base_repository import BaseRepository


class HookPatternsRepository(BaseRepository[HookPattern]):
    model = HookPattern

    def list_for_post(self, post_id: uuid.UUID) -> List[HookPattern]:
        with get_session() as session:
            stmt = select(HookPattern).where(HookPattern.post_id == post_id)
            return list(session.scalars(stmt).all())

    def list_for_category(self, category: str, limit: int = 200) -> List[HookPattern]:
        with get_session() as session:
            stmt = (
                select(HookPattern)
                .where(HookPattern.category == category)
                .order_by(HookPattern.created_at.desc())
                .limit(limit)
            )
            return list(session.scalars(stmt).all())


class HookStatisticsRepository(BaseRepository[HookStatistic]):
    model = HookStatistic

    def get_by_category_hook_type(self, category: str, hook_type: str) -> Optional[HookStatistic]:
        with get_session() as session:
            stmt = select(HookStatistic).where(
                HookStatistic.category == category,
                HookStatistic.hook_type == hook_type,
            )
            return session.scalars(stmt).first()

    def list_for_category(self, category: str) -> List[HookStatistic]:
        with get_session() as session:
            stmt = select(HookStatistic).where(HookStatistic.category == category)
            return list(session.scalars(stmt).all())

    def list_rules(self) -> List[HookStatistic]:
        with get_session() as session:
            stmt = select(HookStatistic).where(HookStatistic.is_rule.is_(True))
            return list(session.scalars(stmt).all())


hook_patterns_repository = HookPatternsRepository()
hook_statistics_repository = HookStatisticsRepository()
