"""
Query / Read Layer for Observations.

Retrieves read models directly from the ORM without passing through the
domain layer.  No business logic; pure data retrieval.

This is intentionally a separate class from the write-side repository
so query concerns don't leak into the write path (CQRS-lite).
"""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from observation.infrastructure.orm.models import ObservationORM
from observation.infrastructure.repository.read_models import (
    ObservationReadModel,
    ObservationSummary,
)


class ObservationQueryService:
    """
    Read-only query service.
    Accepts a SQLAlchemy Session; returns read models, never domain objects.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_by_id(self, observation_id: UUID) -> Optional[ObservationReadModel]:
        """Return full read model by primary key, or None."""
        row = self._session.get(ObservationORM, observation_id)
        if row is None:
            return None
        return self._to_read_model(row)

    def get_by_fingerprint(self, fingerprint: str) -> Optional[ObservationReadModel]:
        """Return full read model by deterministic fingerprint, or None."""
        row = (
            self._session.query(ObservationORM)
            .filter(ObservationORM.fingerprint == fingerprint)
            .first()
        )
        if row is None:
            return None
        return self._to_read_model(row)

    def list_by_tenant(
        self,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ObservationSummary]:
        """Return a page of summaries for a tenant, ordered by fingerprint (stable)."""
        rows = (
            self._session.query(ObservationORM)
            .filter(ObservationORM.tenant_id == tenant_id)
            .order_by(ObservationORM.fingerprint)
            .limit(limit)
            .offset(offset)
            .all()
        )
        return [self._to_summary(r) for r in rows]

    def exists_by_fingerprint(self, fingerprint: str) -> bool:
        """Return True if a fingerprint is already stored (duplicate check)."""
        return (
            self._session.query(ObservationORM.id)
            .filter(ObservationORM.fingerprint == fingerprint)
            .first()
        ) is not None

    # ------------------------------------------------------------------
    # Private converters (ORM → read model)
    # ------------------------------------------------------------------

    @staticmethod
    def _to_read_model(row: ObservationORM) -> ObservationReadModel:
        return ObservationReadModel(
            id=row.id,
            fingerprint=row.fingerprint,
            execution_id=row.execution_id,
            workflow_id=row.workflow_id,
            node_id=row.node_id,
            tenant_id=row.tenant_id,
            payload=row.payload or {},
            status=row.status,
            schema_version=row.schema_version,
            observation_version=row.observation_version,
        )

    @staticmethod
    def _to_summary(row: ObservationORM) -> ObservationSummary:
        return ObservationSummary(
            id=row.id,
            fingerprint=row.fingerprint,
            tenant_id=row.tenant_id,
            status=row.status,
            observation_version=row.observation_version,
        )
