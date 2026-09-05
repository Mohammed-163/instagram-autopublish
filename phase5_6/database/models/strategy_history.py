from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class StrategyHistory(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Every change to overall content strategy, with the before/after
    state and the reason, written by the future Strategy Engine."""

    __tablename__ = "strategy_history"

    strategy_name: Mapped[str] = mapped_column(Text, nullable=False)
    changed_from: Mapped[Optional[dict]] = mapped_column(JSONB)
    changed_to: Mapped[dict] = mapped_column(JSONB, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
