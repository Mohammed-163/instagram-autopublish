from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class Design(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "designs"

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    image_source: Mapped[Optional[str]] = mapped_column(Text)
    image_url: Mapped[Optional[str]] = mapped_column(Text)
    background_type: Mapped[Optional[str]] = mapped_column(Text)
    dominant_color: Mapped[Optional[str]] = mapped_column(Text)
    brightness: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3))
    contrast: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3))
    font_family: Mapped[Optional[str]] = mapped_column(Text)
    font_size: Mapped[Optional[int]] = mapped_column(Integer)
    font_color: Mapped[Optional[str]] = mapped_column(Text)
    shadow: Mapped[bool] = mapped_column(Boolean, default=False)
    alignment: Mapped[Optional[str]] = mapped_column(Text)
    line_count: Mapped[Optional[int]] = mapped_column(Integer)
    word_count: Mapped[Optional[int]] = mapped_column(Integer)
    image_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3))

    post: Mapped["Post"] = relationship(back_populates="designs")  # noqa: F821
