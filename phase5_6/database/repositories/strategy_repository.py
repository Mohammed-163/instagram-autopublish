from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import func, select

from database.client import get_session
from database.models import StrategyCandidate, WeeklyStrategyVersion
from database.repositories.base_repository import BaseRepository


class WeeklyStrategyVersionsRepository(BaseRepository[WeeklyStrategyVersion]):
    model = WeeklyStrategyVersion

    def next_version_number(self) -> int:
        with get_session() as session:
            stmt = select(func.max(WeeklyStrategyVersion.version_number))
            current_max = session.scalar(stmt)
            return int(current_max or 0) + 1

    def get_latest(self) -> Optional[WeeklyStrategyVersion]:
        with get_session() as session:
            stmt = select(WeeklyStrategyVersion).order_by(WeeklyStrategyVersion.version_number.desc())
            return session.scalars(stmt).first()

    def list_recent(self, limit: int = 10) -> List[WeeklyStrategyVersion]:
        with get_session() as session:
            stmt = (
                select(WeeklyStrategyVersion)
                .order_by(WeeklyStrategyVersion.version_number.desc())
                .limit(limit)
            )
            return list(session.scalars(stmt).all())


class StrategyCandidatesRepository(BaseRepository[StrategyCandidate]):
    model = StrategyCandidate

    def list_for_version(self, strategy_version_id: uuid.UUID) -> List[StrategyCandidate]:
        with get_session() as session:
            stmt = (
                select(StrategyCandidate)
                .where(StrategyCandidate.strategy_version_id == strategy_version_id)
                .order_by(StrategyCandidate.position.asc())
            )
            return list(session.scalars(stmt).all())


weekly_strategy_versions_repository = WeeklyStrategyVersionsRepository()
strategy_candidates_repository = StrategyCandidatesRepository()
