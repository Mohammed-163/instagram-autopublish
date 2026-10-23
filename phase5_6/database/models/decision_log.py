from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class DecisionLog(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Every autonomous decision the system makes (best time, best topic,
    best opening line, ...), with the context it saw and why it chose what
    it chose. This is the raw material for the future Explainability Engine."""

    __tablename__ = "decision_logs"

    decision_type: Mapped[str] = mapped_column(Text, nullable=False)
    related_post_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("posts.id", ondelete="SET NULL")
    )
    context: Mapped[Optional[dict]] = mapped_column(JSONB)
    chosen_action: Mapped[Optional[dict]] = mapped_column(JSONB)
    reasoning: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))

    post: Mapped[Optional["Post"]] = relationship()  # noqa: F821
