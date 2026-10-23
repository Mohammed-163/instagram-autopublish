"""
ORM ↔ Domain Mapper.

Responsible for converting between ObservationORM persistence models and
Observation domain objects.  No business logic; pure structural translation.
"""
from __future__ import annotations

from observation.domain.models import (
    ExecutionContext,
    Observation,
    ObservationFingerprint,
    ObservationStatus,
)
from observation.infrastructure.orm.models import ObservationORM


class ObservationMapper:
    """
    Bidirectional mapper between the ORM layer and the domain layer.
    Neither side knows about the other outside this class.
    """

    # ------------------------------------------------------------------
    # ORM → Domain
    # ------------------------------------------------------------------

    @staticmethod
    def to_domain(orm: ObservationORM) -> Observation:
        """Convert a persisted ORM row to an immutable domain Observation."""
        context = ExecutionContext(
            execution_id=orm.execution_id,
            workflow_id=orm.workflow_id,
            node_id=orm.node_id,
            tenant_id=orm.tenant_id,
            extra=orm.context_extra or {},
        )
        return Observation(
            id=orm.id,
            fingerprint=ObservationFingerprint(value=orm.fingerprint),
            context=context,
            payload=orm.payload or {},
            status=ObservationStatus(orm.status),
            schema_version=orm.schema_version,
            observation_version=orm.observation_version,
        )

    # ------------------------------------------------------------------
    # Domain → ORM
    # ------------------------------------------------------------------

    @staticmethod
    def to_orm(domain: Observation) -> ObservationORM:
        """Convert a domain Observation to a new (or updated) ORM row."""
        return ObservationORM(
            id=domain.id,
            fingerprint=domain.fingerprint.value,
            execution_id=domain.context.execution_id,
            workflow_id=domain.context.workflow_id,
            node_id=domain.context.node_id,
            tenant_id=domain.context.tenant_id,
            payload=domain.payload,
            context_extra=domain.context.extra,
            status=domain.status.value,
            schema_version=domain.schema_version,
            observation_version=domain.observation_version,
        )

    @staticmethod
    def update_orm(orm: ObservationORM, domain: Observation) -> None:
        """Apply domain field changes onto an existing ORM row (in-place)."""
        orm.status = domain.status.value
        orm.payload = domain.payload
        orm.context_extra = domain.context.extra
        orm.observation_version = domain.observation_version
