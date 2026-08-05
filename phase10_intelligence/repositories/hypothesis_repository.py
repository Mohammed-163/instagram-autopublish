"""
HypothesisRepository

Repository responsibility: persistence ONLY. No business rules,
thresholds, or scoring logic may appear here -- that belongs in services.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from ..domain.models import Hypothesis
from ..domain.enums import HypothesisStatus
from ..orm.models import HypothesisORM


class HypothesisRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, hypothesis: Hypothesis) -> Hypothesis:
        row = HypothesisORM(
            key=hypothesis.key,
            statement=hypothesis.statement,
            origin_opportunity_id=hypothesis.origin_opportunity_id,
            status=hypothesis.status.value,
            confidence=hypothesis.confidence,
            cycles_active=hypothesis.cycles_active,
            fingerprint=hypothesis.fingerprint,
            version=hypothesis.version,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_domain(row)

    def get_by_key(self, key: str) -> Optional[Hypothesis]:
        row = self._session.query(HypothesisORM).filter_by(key=key).one_or_none()
        return self._to_domain(row) if row else None

    def list_by_status(self, status: HypothesisStatus) -> List[Hypothesis]:
        rows = self._session.query(HypothesisORM).filter_by(status=status.value).all()
        return [self._to_domain(r) for r in rows]

    def update_status(self, key: str, status: HypothesisStatus, cycles_active: Optional[int] = None) -> None:
        row = self._session.query(HypothesisORM).filter_by(key=key).one()
        row.status = status.value
        if cycles_active is not None:
            row.cycles_active = cycles_active
        self._session.flush()

    @staticmethod
    def _to_domain(row: HypothesisORM) -> Hypothesis:
        return Hypothesis(
            id=row.id, key=row.key, statement=row.statement,
            origin_opportunity_id=row.origin_opportunity_id,
            status=HypothesisStatus(row.status), confidence=row.confidence,
            cycles_active=row.cycles_active, fingerprint=row.fingerprint, version=row.version,
        )
