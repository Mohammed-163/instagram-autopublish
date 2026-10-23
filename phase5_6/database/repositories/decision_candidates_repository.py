from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select

from database.client import get_session
from database.models.decision_candidate import DecisionCandidateRecord, DecisionTransition
from database.repositories.base_repository import BaseRepository


class DecisionCandidatesRepository(BaseRepository[DecisionCandidateRecord]):
    model = DecisionCandidateRecord

    def get_by_status(self, status: str) -> List[DecisionCandidateRecord]:
        """Return all decision candidates with the given status, highest score first."""
        with get_session() as session:
            stmt = (
                select(DecisionCandidateRecord)
                .where(DecisionCandidateRecord.status == status)
                .order_by(DecisionCandidateRecord.decision_score.desc())
            )
            return list(session.scalars(stmt).all())

    def get_by_fingerprint(self, fingerprint: str) -> Optional[DecisionCandidateRecord]:
        """Return a persisted decision candidate by fingerprint for deduplication."""
        with get_session() as session:
            stmt = select(DecisionCandidateRecord).where(DecisionCandidateRecord.fingerprint == fingerprint)
            return session.scalars(stmt).first()

    def get_by_strategy_version(self, strategy_version_id: uuid.UUID) -> List[DecisionCandidateRecord]:
        with get_session() as session:
            stmt = select(DecisionCandidateRecord).where(
                DecisionCandidateRecord.strategy_version_id == str(strategy_version_id)
            )
            return list(session.scalars(stmt).all())

    def update_status(
        self,
        decision_candidate_id: uuid.UUID,
        status: str,
        decided_reason: Optional[str] = None,
        decided_by: str = "system",
        decided_at: Optional[datetime] = None,
    ) -> Optional[DecisionCandidateRecord]:
        """Transition a decision candidate to a new lifecycle status."""
        with get_session() as session:
            record = session.get(DecisionCandidateRecord, decision_candidate_id)
            if record:
                record.status = status
                record.decided_reason = decided_reason
                record.decided_by = decided_by
                record.decided_at = decided_at or datetime.now(timezone.utc)
                record.updated_at = datetime.now(timezone.utc)
                session.flush()
                session.refresh(record)
            return record


decision_candidates_repository = DecisionCandidatesRepository()


class DecisionTransitionsRepository(BaseRepository[DecisionTransition]):
    model = DecisionTransition

    def get_by_decision(self, decision_candidate_id: uuid.UUID) -> List[DecisionTransition]:
        """Return full transition history for a decision candidate, ordered chronologically."""
        with get_session() as session:
            stmt = (
                select(DecisionTransition)
                .where(DecisionTransition.decision_candidate_id == str(decision_candidate_id))
                .order_by(DecisionTransition.transition_time.asc())
            )
            return list(session.scalars(stmt).all())


decision_transitions_repository = DecisionTransitionsRepository()
