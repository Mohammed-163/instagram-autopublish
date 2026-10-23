"""
FeedbackRepository

Repository responsibility: persistence ONLY. No business rules,
thresholds, or scoring logic may appear here -- that belongs in services.
"""
from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from ..domain.models import FeedbackRecord
from ..orm.models import FeedbackRecordORM


class FeedbackRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, record: FeedbackRecord) -> FeedbackRecord:
        row = FeedbackRecordORM(
            subject_type=record.subject_type, subject_key=record.subject_key,
            outcome_score=record.outcome_score, applied_learning_rate=record.applied_learning_rate,
            fingerprint=record.fingerprint, version=record.version,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_domain(row)

    def list_for_subject(self, subject_type: str, subject_key: str) -> List[FeedbackRecord]:
        rows = (
            self._session.query(FeedbackRecordORM)
            .filter_by(subject_type=subject_type, subject_key=subject_key)
            .all()
        )
        return [self._to_domain(r) for r in rows]

    def list_recent(self, limit: int) -> List[FeedbackRecord]:
        rows = self._session.query(FeedbackRecordORM).order_by(FeedbackRecordORM.id.desc()).limit(limit).all()
        return [self._to_domain(r) for r in rows]

    @staticmethod
    def _to_domain(row: FeedbackRecordORM) -> FeedbackRecord:
        return FeedbackRecord(
            id=row.id, subject_type=row.subject_type, subject_key=row.subject_key,
            outcome_score=row.outcome_score, applied_learning_rate=row.applied_learning_rate,
            fingerprint=row.fingerprint, version=row.version,
        )
