"""
SQLAlchemy implementation of the ObservationRepository port.
Translates between domain objects and ORM models using ObservationMapper.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from observation.domain.models import Observation, ObservationFingerprint
from observation.domain.repository import ObservationRepository
from observation.infrastructure.orm.mapper import ObservationMapper
from observation.infrastructure.orm.models import ObservationORM


class SQLAlchemyObservationRepository(ObservationRepository):
    """Concrete repository backed by a SQLAlchemy Session."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._mapper = ObservationMapper()

    # ------------------------------------------------------------------
    # ObservationRepository implementation
    # ------------------------------------------------------------------

    def save(self, observation: Observation) -> None:
        orm_obj = ObservationMapper.to_orm(observation)
        self._session.add(orm_obj)
        self._session.flush()  # propagate without committing (UoW owns commit)

    def find_by_id(self, observation_id: UUID) -> Optional[Observation]:
        orm_obj = self._session.get(ObservationORM, observation_id)
        if orm_obj is None:
            return None
        return ObservationMapper.to_domain(orm_obj)

    def find_by_fingerprint(
        self, fingerprint: ObservationFingerprint
    ) -> Optional[Observation]:
        orm_obj = (
            self._session.query(ObservationORM)
            .filter(ObservationORM.fingerprint == fingerprint.value)
            .first()
        )
        if orm_obj is None:
            return None
        return ObservationMapper.to_domain(orm_obj)

    def update(self, observation: Observation) -> None:
        orm_obj = self._session.get(ObservationORM, observation.id)
        if orm_obj is None:
            raise ValueError(
                f"Cannot update non-existent Observation {observation.id}"
            )
        ObservationMapper.update_orm(orm_obj, observation)
        self._session.flush()
