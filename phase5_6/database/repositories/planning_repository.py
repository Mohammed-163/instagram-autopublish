from __future__ import annotations

from datetime import date
from typing import List, Optional

from sqlalchemy import select

from database.client import get_session
from database.models import StrategyHistory, WeeklyPlan
from database.repositories.base_repository import BaseRepository


class WeeklyPlansRepository(BaseRepository[WeeklyPlan]):
    model = WeeklyPlan

    def get_by_week_start(self, week_start_date: date) -> Optional[WeeklyPlan]:
        with get_session() as session:
            stmt = select(WeeklyPlan).where(WeeklyPlan.week_start_date == week_start_date)
            return session.scalars(stmt).first()

    def get_active(self) -> Optional[WeeklyPlan]:
        with get_session() as session:
            stmt = select(WeeklyPlan).where(WeeklyPlan.status == "active").order_by(
                WeeklyPlan.week_start_date.desc()
            )
            return session.scalars(stmt).first()


class StrategyHistoryRepository(BaseRepository[StrategyHistory]):
    model = StrategyHistory

    def list_for_strategy(self, strategy_name: str) -> List[StrategyHistory]:
        with get_session() as session:
            stmt = select(StrategyHistory).where(StrategyHistory.strategy_name == strategy_name).order_by(
                StrategyHistory.effective_at.desc()
            )
            return list(session.scalars(stmt).all())


weekly_plans_repository = WeeklyPlansRepository()
strategy_history_repository = StrategyHistoryRepository()
