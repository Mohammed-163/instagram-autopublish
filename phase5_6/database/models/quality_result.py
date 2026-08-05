from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base, UUIDPrimaryKeyMixin


class QualityResult(UUIDPrimaryKeyMixin, Base):
    """Outcome of a single Quality Gate check run against a candidate post
    before it is allowed to move to 'ready'. Multiple rows per post: one
    per gate, and re-checked every regeneration attempt."""

    __tablename__ = "quality_results"

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    gate_name: Mapped[str] = mapped_column(Text, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3))
    details: Mapped[Optional[dict]] = mapped_column(JSONB)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    post: Mapped["Post"] = relationship()  # noqa: F821
