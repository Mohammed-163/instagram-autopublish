from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

STATUS_VALUES = ("planned", "running", "completed", "aborted")


class Experiment(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A concrete, run-able test of a Hypothesis, with its config and result."""

    __tablename__ = "experiments"

    hypothesis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hypotheses.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    variant_config: Mapped[Optional[dict]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, default="planned")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    result_summary: Mapped[Optional[str]] = mapped_column(Text)
    result_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    hypothesis: Mapped["Hypothesis"] = relationship(back_populates="experiments")  # noqa: F821
