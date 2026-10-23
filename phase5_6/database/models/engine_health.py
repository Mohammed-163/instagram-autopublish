from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base, UUIDPrimaryKeyMixin, UpdatedAtMixin

STATUS_VALUES = ("unknown", "healthy", "degraded", "down")


class EngineHealth(UUIDPrimaryKeyMixin, UpdatedAtMixin, Base):
    """One row per named engine (Observation, Scoring, Decision, ...) with
    its last heartbeat, so a future Health Engine (and Telegram digests)
    can report which parts of the learning loop are actually running."""

    __tablename__ = "engine_health"

    engine_name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="unknown")
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB)
