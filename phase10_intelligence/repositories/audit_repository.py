"""
AuditRepository

Repository responsibility: persistence ONLY. No business rules,
thresholds, or scoring logic may appear here -- that belongs in services.
"""
from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from ..domain.models import AuditEntry
from ..orm.models import AuditEntryORM


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, entry: AuditEntry) -> AuditEntry:
        row = AuditEntryORM(
            event_type=entry.event_type, subject_type=entry.subject_type,
            subject_key=entry.subject_key, fingerprint=entry.fingerprint,
            payload=dict(entry.payload), version=entry.version,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_domain(row)

    def list_for_subject(self, subject_type: str, subject_key: str) -> List[AuditEntry]:
        rows = (
            self._session.query(AuditEntryORM)
            .filter_by(subject_type=subject_type, subject_key=subject_key)
            .order_by(AuditEntryORM.id.asc())
            .all()
        )
        return [self._to_domain(r) for r in rows]

    @staticmethod
    def _to_domain(row: AuditEntryORM) -> AuditEntry:
        return AuditEntry(
            id=row.id, event_type=row.event_type, subject_type=row.subject_type,
            subject_key=row.subject_key, fingerprint=row.fingerprint,
            payload=row.payload, version=row.version,
        )
