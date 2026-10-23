from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class StrategyCandidate(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One planned (not executed) post slot inside a WeeklyStrategyVersion.
    Fully explainable: category/topic/hook_type/objective/reason/confidence
    /expected_success/is_experiment are all populated by the planning
    engine and never by an LLM."""

    __tablename__ = "strategy_candidates"

    strategy_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("weekly_strategy_versions.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    hook_type: Mapped[str] = mapped_column(Text, nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0"))
    expected_success: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0"))
    is_experiment: Mapped[bool] = mapped_column(Boolean, default=False)
    based_on: Mapped[Optional[dict]] = mapped_column(JSONB)

    strategy_version: Mapped["WeeklyStrategyVersion"] = relationship(back_populates="candidates")  # noqa: F821
