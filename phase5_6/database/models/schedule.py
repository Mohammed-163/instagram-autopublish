from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class PublishingSchedule(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "publishing_schedule"

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    selection_reason: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="pending")

    post: Mapped["Post"] = relationship(back_populates="schedule_entries")  # noqa: F821
