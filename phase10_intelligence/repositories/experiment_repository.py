"""
ExperimentRepository

Repository responsibility: persistence ONLY. No business rules,
thresholds, or scoring logic may appear here -- that belongs in services.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from ..domain.models import Experiment
from ..domain.enums import ExperimentStatus
from ..orm.models import ExperimentORM


class ExperimentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, experiment: Experiment) -> Experiment:
        row = ExperimentORM(
            key=experiment.key,
            hypothesis_id=experiment.hypothesis_id,
            status=experiment.status.value,
            sample_size=experiment.sample_size,
            effect_size=experiment.effect_size,
            p_value=experiment.p_value,
            fingerprint=experiment.fingerprint,
            version=experiment.version,
        )
        self._session.add(row)
        self._session.flush()
        return self._to_domain(row)

    def get_by_key(self, key: str) -> Optional[Experiment]:
        row = self._session.query(ExperimentORM).filter_by(key=key).one_or_none()
        return self._to_domain(row) if row else None

    def list_by_status(self, status: ExperimentStatus) -> List[Experiment]:
        rows = self._session.query(ExperimentORM).filter_by(status=status.value).all()
        return [self._to_domain(r) for r in rows]

    def update(self, key: str, status: ExperimentStatus, sample_size: int,
               effect_size: Optional[float], p_value: Optional[float]) -> None:
        row = self._session.query(ExperimentORM).filter_by(key=key).one()
        row.status = status.value
        row.sample_size = sample_size
        row.effect_size = effect_size
        row.p_value = p_value
        self._session.flush()

    @staticmethod
    def _to_domain(row: ExperimentORM) -> Experiment:
        return Experiment(
            id=row.id, key=row.key, hypothesis_id=row.hypothesis_id,
            status=ExperimentStatus(row.status), sample_size=row.sample_size,
            effect_size=row.effect_size, p_value=row.p_value,
            fingerprint=row.fingerprint, version=row.version,
        )
