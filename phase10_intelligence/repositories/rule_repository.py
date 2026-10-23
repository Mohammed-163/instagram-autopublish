"""
RuleRepository

Repository responsibility: persistence ONLY. No business rules,
thresholds, or scoring logic may appear here -- that belongs in services.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from ..domain.models import Rule
from ..domain.enums import RuleStatus
from ..orm.models import RuleORM


class RuleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, rule: Rule) -> Rule:
        row = RuleORM(
            key=rule.key, condition_expression=rule.condition_expression,
            action_expression=rule.action_expression, status=rule.status.value,
            confidence=rule.confidence, generation=rule.generation,
            fingerprint=rule.fingerprint, version=rule.version,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_domain(row)

    def get_by_key(self, key: str) -> Optional[Rule]:
        row = self._session.query(RuleORM).filter_by(key=key).one_or_none()
        return self._to_domain(row) if row else None

    def list_by_status(self, status: RuleStatus) -> List[Rule]:
        rows = self._session.query(RuleORM).filter_by(status=status.value).all()
        return [self._to_domain(r) for r in rows]

    def count_active(self) -> int:
        return self._session.query(RuleORM).filter_by(status=RuleStatus.ACTIVE.value).count()

    def update_confidence_and_status(self, key: str, confidence: float, status: RuleStatus) -> None:
        row = self._session.query(RuleORM).filter_by(key=key).one()
        row.confidence = confidence
        row.status = status.value
        self._session.flush()

    @staticmethod
    def _to_domain(row: RuleORM) -> Rule:
        return Rule(
            id=row.id, key=row.key, condition_expression=row.condition_expression,
            action_expression=row.action_expression, status=RuleStatus(row.status),
            confidence=row.confidence, generation=row.generation,
            fingerprint=row.fingerprint, version=row.version,
        )
