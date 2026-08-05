from __future__ import annotations

from typing import Optional

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base, UpdatedAtMixin


class SystemSetting(UpdatedAtMixin, Base):
    """Generic key/value config store (feature flags, thresholds, toggles)
    read by any part of the system, keyed by a human-readable string
    instead of a UUID since these are hand-managed, not generated rows."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
