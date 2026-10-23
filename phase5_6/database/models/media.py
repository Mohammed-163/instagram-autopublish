from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class Media(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "media"

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    original_image_url: Mapped[Optional[str]] = mapped_column(Text)
    original_image_source: Mapped[Optional[str]] = mapped_column(Text)
    final_video_url: Mapped[Optional[str]] = mapped_column(Text)
    video_duration_seconds: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    audio_used: Mapped[Optional[str]] = mapped_column(Text)
    instagram_audio_id: Mapped[Optional[str]] = mapped_column(Text)
    audio_reference_url: Mapped[Optional[str]] = mapped_column(Text)

    post: Mapped["Post"] = relationship(back_populates="media_items")  # noqa: F821
