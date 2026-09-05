from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

SEVERITY_VALUES = ("info", "warning", "critical")
STATUS_VALUES = ("pending", "sent", "failed")


class Notification(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Log of every outbound notification (Telegram today, others later),
    decoupled from lib/telegram_notifier.py so a future Notification Policy
    engine can decide what/when to send by querying history, not by guessing."""

    __tablename__ = "notifications"

    channel: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, default="info")
    title: Mapped[Optional[str]] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="pending")
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
