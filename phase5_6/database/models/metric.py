from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import Base, UUIDPrimaryKeyMixin

SNAPSHOT_PERIODS = ("2h", "6h", "24h", "7d")


class Metric(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "metrics"

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_period: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    views: Mapped[Optional[int]] = mapped_column(BigInteger)
    reach: Mapped[Optional[int]] = mapped_column(BigInteger)
    likes: Mapped[Optional[int]] = mapped_column(BigInteger)
    comments: Mapped[Optional[int]] = mapped_column(BigInteger)
    shares: Mapped[Optional[int]] = mapped_column(BigInteger)
    saves: Mapped[Optional[int]] = mapped_column(BigInteger)
    engagement_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 4))
    followers: Mapped[Optional[int]] = mapped_column(BigInteger)
    impressions: Mapped[Optional[int]] = mapped_column(BigInteger)
    profile_visits: Mapped[Optional[int]] = mapped_column(BigInteger)
    accounts_reached: Mapped[Optional[int]] = mapped_column(BigInteger)
    accounts_engaged: Mapped[Optional[int]] = mapped_column(BigInteger)

    post: Mapped["Post"] = relationship(back_populates="metrics")  # noqa: F821
