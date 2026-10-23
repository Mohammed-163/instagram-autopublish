"""
ObservationEngine
=================
1) Observation Engine — Entry point for all data observations.

Responsibility:
- Listen to incoming PostPublished domain events.
- Record the observation via AuditService (never touches a repository directly).
- Publish ObservationRecorded event to trigger feature extraction.

Design:
- Extends EngineBase for heartbeat() and settings access.
- Depends only on AuditService (Service Layer), not on any repository.
- Uses DomainEvent.payload() — the method guaranteed on every event — instead
  of ad-hoc hasattr checks.
"""
from __future__ import annotations

import logging
from typing import Any

from core.events import PostPublished, ObservationRecorded
from engines.shared.engine_base import EngineBase

logger = logging.getLogger(__name__)


class ObservationEngine(EngineBase):
    """
    Entry point for the pipeline.
    Converts PostPublished → ObservationRecorded.
    """

    ENGINE_NAME = "observation"

    def __init__(
        self,
        event_bus: Any,
        audit_service: Any,
        health_service: Any = None,
        settings_service: Any = None,
    ) -> None:
        super().__init__(health_service=health_service, settings_service=settings_service)
        self.event_bus = event_bus
        self.audit_service = audit_service

    def handle_post_published(self, event: PostPublished) -> None:
        """Handle PostPublished: record observation and emit ObservationRecorded."""
        try:
            logger.info("[ObservationEngine] PostPublished observed for post_id: %s", event.post_id)

            # Record observation via Service Layer (not repository)
            payload = event.payload()
            self.audit_service.record_event(
                event_type=event.event_type,
                payload=payload,
            )

            # Emit ObservationRecorded
            observation_event = ObservationRecorded(
                post_id=event.post_id,
                observation_type="post_published",
                payload_data=payload,
            )
            self.event_bus.publish(observation_event)

            self.heartbeat("healthy")
            logger.info("[ObservationEngine] ObservationRecorded published for post_id: %s", event.post_id)

        except Exception as e:
            logger.exception("[ObservationEngine] Error processing PostPublished: %s", e)
            self.heartbeat("error", error=str(e))
