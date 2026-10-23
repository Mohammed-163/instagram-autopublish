from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base, CreatedAtMixin, UpdatedAtMixin, UUIDPrimaryKeyMixin

STATUS_VALUES = ("draft", "ready", "scheduled", "publishing", "published", "failed", "cleaned")


class Post(UUIDPrimaryKeyMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "posts"

    category: Mapped[Optional[str]] = mapped_column(Text)
    topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id", ondelete="SET NULL")
    )
    final_text: Mapped[Optional[str]] = mapped_column(Text)
    prompt_version: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="draft")
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    instagram_media_id: Mapped[Optional[str]] = mapped_column(Text)
    instagram_permalink: Mapped[Optional[str]] = mapped_column(Text)
    plan_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))

    topic: Mapped[Optional["Topic"]] = relationship(back_populates="posts")  # noqa: F821
    designs: Mapped[List["Design"]] = relationship(back_populates="post", cascade="all, delete-orphan")  # noqa: F821
    media_items: Mapped[List["Media"]] = relationship(back_populates="post", cascade="all, delete-orphan")  # noqa: F821
    schedule_entries: Mapped[List["PublishingSchedule"]] = relationship(  # noqa: F821
        back_populates="post", cascade="all, delete-orphan"
    )
    history_entries: Mapped[List["PublishingHistory"]] = relationship(  # noqa: F821
        back_populates="post", cascade="all, delete-orphan"
    )
    metrics: Mapped[List["Metric"]] = relationship(back_populates="post", cascade="all, delete-orphan")  # noqa: F821
