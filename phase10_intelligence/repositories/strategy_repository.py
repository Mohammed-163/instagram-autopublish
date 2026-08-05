"""
StrategyRepository

Repository responsibility: persistence ONLY. No business rules,
thresholds, or scoring logic may appear here -- that belongs in services.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from ..domain.models import Strategy, StrategyEvaluation
from ..domain.enums import StrategyStatus
from ..orm.models import StrategyORM, StrategyEvaluationORM


class StrategyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, strategy: Strategy) -> Strategy:
        row = StrategyORM(
            key=strategy.key, status=strategy.status.value,
            parameters=dict(strategy.parameters), generation=strategy.generation,
            parent_key=strategy.parent_key, fitness_score=strategy.fitness_score,
            fingerprint=strategy.fingerprint, version=strategy.version,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_domain(row)

    def get_by_key(self, key: str) -> Optional[Strategy]:
        row = self._session.query(StrategyORM).filter_by(key=key).one_or_none()
        return self._to_domain(row) if row else None

    def list_by_status(self, status: StrategyStatus) -> List[Strategy]:
        rows = self._session.query(StrategyORM).filter_by(status=status.value).all()
        return [self._to_domain(r) for r in rows]

    def list_top_by_fitness(self, limit: int) -> List[Strategy]:
        rows = (
            self._session.query(StrategyORM)
            .order_by(StrategyORM.fitness_score.desc(), StrategyORM.key.asc())
            .limit(limit)
            .all()
        )
        return [self._to_domain(r) for r in rows]

    def update_status_and_fitness(self, key: str, status: StrategyStatus, fitness_score: float) -> None:
        row = self._session.query(StrategyORM).filter_by(key=key).one()
        row.status = status.value
        row.fitness_score = fitness_score
        self._session.flush()

    def add_evaluation(self, evaluation: StrategyEvaluation) -> StrategyEvaluation:
        row = StrategyEvaluationORM(
            strategy_id=evaluation.strategy_id, fitness_score=evaluation.fitness_score,
            metrics=dict(evaluation.metrics), fingerprint=evaluation.fingerprint,
            version=evaluation.version,
        )
        self._session.add(row)
        self._session.flush()
        return StrategyEvaluation(
            id=row.id, strategy_id=row.strategy_id, fitness_score=row.fitness_score,
            metrics=row.metrics, fingerprint=row.fingerprint, version=row.version,
        )

    @staticmethod
    def _to_domain(row: StrategyORM) -> Strategy:
        return Strategy(
            id=row.id, key=row.key, status=StrategyStatus(row.status),
            parameters=row.parameters, generation=row.generation, parent_key=row.parent_key,
            fitness_score=row.fitness_score, fingerprint=row.fingerprint, version=row.version,
        )
