from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

STATUS_VALUES = ("draft", "active", "completed", "superseded")


class WeeklyPlan(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """The strategic plan produced at the start of each week by the future
    Weekly Planner engine; becomes the reference for that week's posts."""

    __tablename__ = "weekly_plans"

    week_start_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    week_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    plan: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="draft")
