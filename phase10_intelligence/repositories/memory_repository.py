"""
MemoryRepository

Repository responsibility: persistence ONLY. No business rules,
thresholds, or scoring logic may appear here -- that belongs in services.
"""
from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from ..domain.models import MemoryRecord
from ..orm.models import MemoryRecordORM


class MemoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, record: MemoryRecord) -> MemoryRecord:
        row = MemoryRecordORM(
            subject_type=record.subject_type, subject_key=record.subject_key,
            payload=dict(record.payload), relevance_score=record.relevance_score,
            fingerprint=record.fingerprint, version=record.version,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_domain(row)

    def list_relevant(self, subject_type: str, min_relevance: float) -> List[MemoryRecord]:
        rows = (
            self._session.query(MemoryRecordORM)
            .filter(MemoryRecordORM.subject_type == subject_type)
            .filter(MemoryRecordORM.relevance_score >= min_relevance)
            .order_by(MemoryRecordORM.relevance_score.desc())
            .all()
        )
        return [self._to_domain(r) for r in rows]

    def count(self) -> int:
        return self._session.query(MemoryRecordORM).count()

    def prune_lowest(self, keep_limit: int) -> int:
        total = self.count()
        if total <= keep_limit:
            return 0
        excess = total - keep_limit
        rows_to_delete = (
            self._session.query(MemoryRecordORM)
            .order_by(MemoryRecordORM.relevance_score.asc(), MemoryRecordORM.id.asc())
            .limit(excess)
            .all()
        )
        for row in rows_to_delete:
            self._session.delete(row)
        self._session.flush()
        return len(rows_to_delete)

    @staticmethod
    def _to_domain(row: MemoryRecordORM) -> MemoryRecord:
        return MemoryRecord(
            id=row.id, subject_type=row.subject_type, subject_key=row.subject_key,
            payload=row.payload, relevance_score=row.relevance_score,
            fingerprint=row.fingerprint, version=row.version,
        )
