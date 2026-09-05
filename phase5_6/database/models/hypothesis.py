from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import DateTime, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

STATUS_VALUES = ("open", "testing", "confirmed", "rejected", "inconclusive")


class Hypothesis(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A candidate belief awaiting experimental validation, e.g. 'shorter
    hooks perform better on weekday mornings'. The Hypothesis Engine
    (Phase 2) will create these; the Experiment Engine will test them."""

    __tablename__ = "hypotheses"

    statement: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="open")
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    evaluated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    experiments: Mapped[List["Experiment"]] = relationship(  # noqa: F821
        back_populates="hypothesis", cascade="all, delete-orphan"
    )
