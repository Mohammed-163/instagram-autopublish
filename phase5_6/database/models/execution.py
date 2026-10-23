"""
Execution Layer Models — Phase 6 Part 1.

Two models only:
  - ExecutionRecord      : persisted execution lifecycle record
  - ExecutionTransition  : immutable audit log of every status change

Lifecycle states:
  Pending → Scheduled → Running → Completed
                                → Failed
  Pending   → Cancelled
  Scheduled → Cancelled
  Pending   → Expired
  Scheduled → Expired

Every transition stores: reason, versions, timestamp, actor (Explainability rule).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base, UUIDPrimaryKeyMixin, CreatedAtMixin


class ExecutionRecord(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One execution attempt spawned from an approved DecisionCandidate.

    Status machine (8 allowed transitions only — all others rejected):
      Pending   → Scheduled
      Scheduled → Running
      Running   → Completed
      Running   → Failed
      Pending   → Cancelled
      Scheduled → Cancelled
      Pending   → Expired
      Scheduled → Expired
    """

    __tablename__ = "execution_records"

    # Source decision
    decision_candidate_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))

    # Lifecycle — initial state is always Pending
    status: Mapped[str] = mapped_column(Text, nullable=False, default="Pending")

    # Classification
    execution_type: Mapped[str] = mapped_column(Text, nullable=False)
    objective_profile: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Deduplication (deterministic fingerprint)
    fingerprint: Mapped[Optional[str]] = mapped_column(Text)
    fingerprint_version: Mapped[Optional[str]] = mapped_column(Text)

    # Rich context forwarded from the approved decision
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata_", JSONB, nullable=False, default=dict)
    versions: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    explainability: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # Outcome
    result: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text)

    # Timing (populated as lifecycle progresses)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    expired_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class ExecutionTransition(UUIDPrimaryKeyMixin, Base):
    """Immutable record of a single status transition on an ExecutionRecord.

    Explainability invariant: every row must store reason, versions, actor,
    and transitioned_at so the full lifecycle is auditable and replayable.
    """

    __tablename__ = "execution_transitions"

    execution_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)

    from_status: Mapped[Optional[str]] = mapped_column(Text)  # NULL for initial Pending
    to_status: Mapped[str] = mapped_column(Text, nullable=False)

    # Explainability fields (all required per architecture rule)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    actor: Mapped[str] = mapped_column(Text, nullable=False, default="system")
    versions: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    transitioned_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
