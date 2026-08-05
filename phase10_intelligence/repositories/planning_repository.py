"""
PlanningRepository

Repository responsibility: persistence ONLY. No business rules,
thresholds, or scoring logic may appear here -- that belongs in services.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from ..domain.models import PlanningCycle
from ..orm.models import PlanningCycleORM


class PlanningRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, cycle: PlanningCycle) -> PlanningCycle:
        row = PlanningCycleORM(
            cycle_index=cycle.cycle_index, horizon=cycle.horizon,
            selected_strategy_keys=list(cycle.selected_strategy_keys),
            risk_budget_used=cycle.risk_budget_used,
            fingerprint=cycle.fingerprint, version=cycle.version,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_domain(row)

    def latest(self) -> Optional[PlanningCycle]:
        row = self._session.query(PlanningCycleORM).order_by(PlanningCycleORM.cycle_index.desc()).first()
        return self._to_domain(row) if row else None

    def list_all(self) -> List[PlanningCycle]:
        rows = self._session.query(PlanningCycleORM).order_by(PlanningCycleORM.cycle_index.asc()).all()
        return [self._to_domain(r) for r in rows]

    @staticmethod
    def _to_domain(row: PlanningCycleORM) -> PlanningCycle:
        return PlanningCycle(
            id=row.id, cycle_index=row.cycle_index, horizon=row.horizon,
            selected_strategy_keys=row.selected_strategy_keys,
            risk_budget_used=row.risk_budget_used, fingerprint=row.fingerprint, version=row.version,
        )
