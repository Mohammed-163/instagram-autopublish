from __future__ import annotations

from datetime import date
from typing import List, Optional

from sqlalchemy import Date, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

STRATEGY_STATUS_VALUES = ("planned", "reviewed", "superseded")


class WeeklyStrategyVersion(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A versioned, immutable snapshot of one weekly strategy planning run.
    Produced by StrategyPlanningEngine. Planning-only: never executes any
    publishing decision, only records what the plan recommends."""

    __tablename__ = "weekly_strategy_versions"

    version_number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    week_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="planned")
    summary: Mapped[Optional[str]] = mapped_column(Text)

    candidates: Mapped[List["StrategyCandidate"]] = relationship(  # noqa: F821
        back_populates="strategy_version", cascade="all, delete-orphan"
    )
