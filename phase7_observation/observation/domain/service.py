"""
Observation domain service.
Orchestrates fingerprint generation, duplicate detection, and persistence
using only domain objects and ports.  No infrastructure imports.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict

from observation.domain.event_publisher import EventPublisher
from observation.domain.events import (
    ExecutionCompleted,
    ObservationDuplicated,
    ObservationRecorded,
)
from observation.domain.models import (
    ExecutionContext,
    Observation,
    ObservationFingerprint,
    ObservationStatus,
)
from observation.domain.repository import ObservationRepository


class ObservationService:
    """
    Core domain service: record observations idempotently.
    Business logic lives here; infrastructure concerns do not.
    """

    def __init__(
        self,
        repository: ObservationRepository,
        publisher: EventPublisher,
        observation_version: str,
        fingerprint_version: str,
    ) -> None:
        self._repository = repository
        self._publisher = publisher
        self._observation_version = observation_version
        self._fingerprint_version = fingerprint_version

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_from_execution(self, event: ExecutionCompleted) -> Observation:
        """
        Idempotently record an observation derived from ExecutionCompleted.
        Returns the Observation (new or existing duplicate).
        """
        context = ExecutionContext(
            execution_id=event.execution_id,
            workflow_id=event.workflow_id,
            node_id=event.node_id,
            tenant_id=event.tenant_id,
        )

        fingerprint_payload = {
            "context": context.as_dict(),
            "payload": dict(sorted(event.payload.items())),
        }
        fingerprint = ObservationFingerprint.from_payload(
            fingerprint_payload, self._fingerprint_version
        )

        # Idempotency: check for existing fingerprint
        existing = self._repository.find_by_fingerprint(fingerprint)
        if existing is not None:
            duplicated = existing.mark_duplicate()
            self._publisher.publish(
                ObservationDuplicated(
                    fingerprint=fingerprint.value,
                    tenant_id=event.tenant_id,
                )
            )
            return duplicated

        observation = Observation(
            id=uuid.uuid4(),
            fingerprint=fingerprint,
            context=context,
            payload=dict(event.payload),
            status=ObservationStatus.PENDING,
            schema_version="1.0",
            observation_version=self._observation_version,
        )
        recorded = observation.mark_recorded()
        self._repository.save(recorded)
        self._publisher.publish(
            ObservationRecorded(
                observation_id=recorded.id,
                fingerprint=fingerprint.value,
                tenant_id=event.tenant_id,
                payload=dict(event.payload),
            )
        )
        return recorded
