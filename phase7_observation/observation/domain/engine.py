"""
ObservationEngine — the top-level domain façade.
Accepts inbound events and delegates to ObservationService.
This is the single entry point from the application layer into the domain.
"""
from __future__ import annotations

from observation.domain.events import DomainEvent, ExecutionCompleted
from observation.domain.models import Observation
from observation.domain.service import ObservationService


class ObservationEngine:
    """
    Thin façade that routes inbound domain events to the appropriate
    domain service method.  Contains no business logic of its own.
    """

    def __init__(self, service: ObservationService) -> None:
        self._service = service

    def handle(self, event: DomainEvent) -> None:
        """
        Dispatch an inbound domain event.
        Currently handles: ExecutionCompleted.
        """
        if isinstance(event, ExecutionCompleted):
            self._handle_execution_completed(event)
        else:
            raise ValueError(
                f"ObservationEngine: unhandled event type '{type(event).__name__}'"
            )

    # ------------------------------------------------------------------
    # Private handlers
    # ------------------------------------------------------------------

    def _handle_execution_completed(self, event: ExecutionCompleted) -> Observation:
        return self._service.record_from_execution(event)
