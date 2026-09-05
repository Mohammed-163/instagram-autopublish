from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin, UpdatedAtMixin


class MemoryEntry(UUIDPrimaryKeyMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    """Long-lived key/value knowledge the system recalls across learning
    cycles (the Memory Engine's storage), separate from knowledge_rules
    because memory is raw recall, not an executable decision rule."""

    __tablename__ = "memory_entries"

    memory_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    memory_value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(Text)
    importance: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.5"))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
