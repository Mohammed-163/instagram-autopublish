from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import DateTime, Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class Topic(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "topics"

    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    current_weight: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("1.0"))
    avg_performance: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    avg_reach: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4))
    avg_saves: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4))
    posts_count: Mapped[int] = mapped_column(Integer, default=0)
    last_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    posts: Mapped[List["Post"]] = relationship(back_populates="topic")  # noqa: F821
