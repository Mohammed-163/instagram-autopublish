from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base, UUIDPrimaryKeyMixin, CreatedAtMixin


class DecisionCandidateRecord(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Persisted decision candidate produced by Phase5DecisionEngine and
    scored/persisted exclusively via Phase5DecisionService."""

    __tablename__ = "decision_candidates"

    strategy_version_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))
    strategy_candidate_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))

    decision_type: Mapped[str] = mapped_column(Text, nullable=False)
    objective_profile: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="Proposed")

    confidence: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    expected_gain: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    risk: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    decision_score: Mapped[float] = mapped_column(Numeric(8, 4), default=0)

    related_opportunities: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)
    explainability: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    versions: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)

    scoring_version: Mapped[Optional[str]] = mapped_column(Text)
    fingerprint: Mapped[Optional[str]] = mapped_column(Text)
    structural_fingerprint: Mapped[Optional[str]] = mapped_column(Text)
    feature_fingerprint: Mapped[Optional[str]] = mapped_column(Text)
    fingerprint_hash: Mapped[Optional[str]] = mapped_column(Text)
    fingerprint_version: Mapped[Optional[str]] = mapped_column(Text)

    decided_reason: Mapped[Optional[str]] = mapped_column(Text)
    decided_by: Mapped[Optional[str]] = mapped_column(Text)
    decided_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))

    proposed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class DecisionTransition(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Records every lifecycle state transition of a DecisionCandidate.

    Phase 5 (Part 2) — Decision Lifecycle Completion. Mirrors
    `database.models.opportunity.OpportunityTransition`. Every status change
    must be logged here with the reason, versions, and explainability
    snapshot in effect at the moment of transition.
    """

    __tablename__ = "decision_transitions"

    decision_candidate_id: Mapped[str] = mapped_column(Text, nullable=False)
    previous_status: Mapped[Optional[str]] = mapped_column(Text)
    new_status: Mapped[str] = mapped_column(Text, nullable=False)
    transition_reason: Mapped[Optional[str]] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(Text, default="system")

    versions: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    explainability_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    transition_time: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
