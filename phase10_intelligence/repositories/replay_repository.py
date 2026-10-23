"""
ReplayRepository

Repository responsibility: persistence ONLY. No business rules,
thresholds, or scoring logic may appear here -- that belongs in services.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from ..domain.models import ReplayRecord
from ..orm.models import ReplayRecordORM


class ReplayRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, record: ReplayRecord) -> ReplayRecord:
        row = ReplayRecordORM(
            subject_type=record.subject_type, subject_key=record.subject_key,
            input_fingerprint=record.input_fingerprint, output_fingerprint=record.output_fingerprint,
            engine_name=record.engine_name, engine_version=record.engine_version,
            version=record.version,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_domain(row)

    def find_by_input_fingerprint(self, input_fingerprint: str) -> Optional[ReplayRecord]:
        row = (
            self._session.query(ReplayRecordORM)
            .filter_by(input_fingerprint=input_fingerprint)
            .order_by(ReplayRecordORM.id.desc())
            .first()
        )
        return self._to_domain(row) if row else None

    def list_for_subject(self, subject_type: str, subject_key: str) -> List[ReplayRecord]:
        rows = (
            self._session.query(ReplayRecordORM)
            .filter_by(subject_type=subject_type, subject_key=subject_key)
            .all()
        )
        return [self._to_domain(r) for r in rows]

    @staticmethod
    def _to_domain(row: ReplayRecordORM) -> ReplayRecord:
        return ReplayRecord(
            id=row.id, subject_type=row.subject_type, subject_key=row.subject_key,
            input_fingerprint=row.input_fingerprint, output_fingerprint=row.output_fingerprint,
            engine_name=row.engine_name, engine_version=row.engine_version, version=row.version,
        )
