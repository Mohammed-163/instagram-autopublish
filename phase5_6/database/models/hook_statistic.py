from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base, UUIDPrimaryKeyMixin, UpdatedAtMixin

SUCCESS_LEVELS = ("low", "medium", "high")


class HookStatistic(UUIDPrimaryKeyMixin, UpdatedAtMixin, Base):
    """Rolling aggregate of hook-type performance per category. This IS the
    'Hook Rule': category -> hook_type -> success_level, built purely from
    observed data (no hard-coded thresholds baked into the row itself —
    success_level/confidence are recomputed from sample statistics each
    time a new observation arrives)."""

    __tablename__ = "hook_statistics"
    __table_args__ = (UniqueConstraint("category", "hook_type", name="uq_hook_statistics_category_hook_type"),)

    category: Mapped[str] = mapped_column(Text, nullable=False)
    hook_type: Mapped[str] = mapped_column(Text, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    success_sum: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0"))
    avg_success_score: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0"))
    success_level: Mapped[str] = mapped_column(Text, default="low")
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0"))
    is_rule: Mapped[bool] = mapped_column(Boolean, default=False)
