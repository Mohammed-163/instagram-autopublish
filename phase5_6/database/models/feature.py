from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class Feature(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A single extracted feature for a post (key/value), written by the
    future Feature Extractor engine. Open-ended by design: new feature keys
    never require a migration, only a new row."""

    __tablename__ = "features"

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    feature_key: Mapped[str] = mapped_column(Text, nullable=False)
    feature_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6))
    feature_value_text: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[Optional[str]] = mapped_column(Text)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    post: Mapped["Post"] = relationship()  # noqa: F821
