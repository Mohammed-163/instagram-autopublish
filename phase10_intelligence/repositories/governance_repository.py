"""
GovernanceRepository

Repository responsibility: persistence ONLY. No business rules,
thresholds, or scoring logic may appear here -- that belongs in services.
"""
from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from ..domain.models import GovernanceReview
from ..domain.enums import GovernanceDecision
from ..orm.models import GovernanceReviewORM


class GovernanceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, review: GovernanceReview) -> GovernanceReview:
        row = GovernanceReviewORM(
            subject_type=review.subject_type, subject_key=review.subject_key,
            decision=review.decision.value, risk_score=review.risk_score,
            approvals=review.approvals, rationale=review.rationale,
            fingerprint=review.fingerprint, version=review.version,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_domain(row)

    def list_for_subject(self, subject_type: str, subject_key: str) -> List[GovernanceReview]:
        rows = (
            self._session.query(GovernanceReviewORM)
            .filter_by(subject_type=subject_type, subject_key=subject_key)
            .all()
        )
        return [self._to_domain(r) for r in rows]

    @staticmethod
    def _to_domain(row: GovernanceReviewORM) -> GovernanceReview:
        return GovernanceReview(
            id=row.id, subject_type=row.subject_type, subject_key=row.subject_key,
            decision=GovernanceDecision(row.decision), risk_score=row.risk_score,
            approvals=row.approvals, rationale=row.rationale,
            fingerprint=row.fingerprint, version=row.version,
        )
