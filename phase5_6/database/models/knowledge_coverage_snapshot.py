from __future__ import annotations

from typing import Any, Dict, Optional
from datetime import datetime

from sqlalchemy import Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base, UUIDPrimaryKeyMixin, CreatedAtMixin


class KnowledgeCoverageSnapshot(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A point-in-time snapshot of the system's knowledge coverage, density, and exploration."""

    __tablename__ = "knowledge_coverage_snapshots"

    calculated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    knowledge_version: Mapped[Optional[str]] = mapped_column(Text)
    coverage_version: Mapped[Optional[str]] = mapped_column(Text)
    
    total_entities: Mapped[int] = mapped_column(Integer, default=0)
    covered_entities: Mapped[int] = mapped_column(Integer, default=0)
    unknown_entities: Mapped[int] = mapped_column(Integer, default=0)
    
    knowledge_coverage: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    knowledge_density: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    exploration_ratio: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    
    confidence_distribution: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    category_distribution: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    feature_distribution: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    notes: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
