from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base, UUIDPrimaryKeyMixin, CreatedAtMixin


class Opportunity(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Persisted opportunity discovered by an Opportunity Detector plugin."""

    __tablename__ = "opportunities"

    parent_opportunity_id: Mapped[Optional[str]] = mapped_column(Text)
    opportunity_type: Mapped[str] = mapped_column(Text, nullable=False)
    detector_name: Mapped[str] = mapped_column(Text, nullable=False)
    detector_version: Mapped[str] = mapped_column(Text, default="1.0.0")
    knowledge_version: Mapped[Optional[str]] = mapped_column(Text)
    coverage_version: Mapped[Optional[str]] = mapped_column(Text)
    scoring_version: Mapped[Optional[str]] = mapped_column(Text)
    settings_version: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="Detected")
    confidence: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    impact: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    novelty: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    knowledge_gap: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    risk: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    opportunity_score: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    expected_gain: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    explainability: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    evidence: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    related_entities: Mapped[List[str]] = mapped_column(JSONB, nullable=False)
    # 'metadata' is a reserved SQLAlchemy name; map to column 'metadata'
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    fingerprint: Mapped[Optional[str]] = mapped_column(Text)
    detected_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class OpportunityTransition(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Records every lifecycle state transition of an Opportunity.

    Every status change must be logged here with timestamp, reason, and actor.
    """

    __tablename__ = "opportunity_transitions"

    opportunity_id: Mapped[str] = mapped_column(Text, nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(Text)
    to_status: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(Text, default="system")
    version: Mapped[Optional[str]] = mapped_column(Text)
    transitioned_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
