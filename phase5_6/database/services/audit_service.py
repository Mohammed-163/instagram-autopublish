from __future__ import annotations
import logging
from typing import List, Optional, Any, Dict

from database.models import EventLog, Failure, ExplainabilityNote
from core.container import container

logger = logging.getLogger(__name__)


class AuditService:
    """Note: publishing/reacting to domain events goes through core.event_bus
    (see core/wiring.py). This service is only the persistence side —
    the audit trail of raw event log rows, failures, and explainability
    notes — not a participant in the pub/sub pipeline itself."""

    def __init__(self, events_repository=None, failures_repository=None, explainability_repository=None) -> None:
        self.events_repository = events_repository or container.resolve("events_repository")
        self.failures_repository = failures_repository or container.resolve("failures_repository")
        self.explainability_repository = explainability_repository or container.resolve("explainability_repository")

    def log_event(self, event_type: str, source: str, payload: Optional[Dict[str, Any]] = None) -> EventLog:
        return self.events_repository.log(event_type=event_type, source=source, payload=payload or {})

    def log_failure(self, source: str, failure_type: str, message: str, context: Optional[Dict[str, Any]] = None) -> Failure:
        return self.failures_repository.create(
            source=source, failure_type=failure_type, message=message, context=context or {}, resolved=False
        )

    def list_recent_events(self, event_type: Optional[str] = None, limit: int = 100) -> List[EventLog]:
        if event_type:
            return self.events_repository.list_by_type(event_type, limit=limit)
        events = self.events_repository.list_all(limit=limit)
        return sorted(events, key=lambda x: x.occurred_at, reverse=True)[:limit]

    def list_unresolved_failures(self) -> List[Failure]:
        return self.failures_repository.list_unresolved()

    def resolve_failure(self, failure_id: Any) -> None:
        self.failures_repository.resolve(failure_id)

    def explain(self, subject_type: str, subject_id: Any, explanation: str, factors: Optional[Dict[str, Any]] = None) -> ExplainabilityNote:
        return self.explainability_repository.create(
            subject_type=subject_type, subject_id=subject_id, explanation=explanation, factors=factors or {}
        )

    def record_event(self, event_type: str, payload: Optional[Dict[str, Any]] = None) -> None:
        """
        Record a domain event observation.
        Wraps log_event with a default source derived from the event type so
        ObservationEngine can record events without touching the repository.
        """
        source = f"observation_engine.{event_type}"
        try:
            self.events_repository.record_event(event_type=event_type, payload=payload or {})
        except AttributeError:
            # Fallback: use the generic log path if record_event is not on repository
            self.log_event(event_type=event_type, source=source, payload=payload or {})


audit_service = AuditService()
