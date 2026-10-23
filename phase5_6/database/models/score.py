from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class Score(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A single computed score for a post (e.g. 'overall_performance',
    'visual_quality'). Multiple score_type/method_version rows can coexist
    per post so scoring methods can evolve without overwriting history."""

    __tablename__ = "scores"

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    score_type: Mapped[str] = mapped_column(Text, nullable=False)
    score_value: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    method_version: Mapped[Optional[str]] = mapped_column(Text)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    post: Mapped["Post"] = relationship()  # noqa: F821
