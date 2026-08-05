"""
Concrete EventPublisher implementations.

Only in-process and logging publishers are provided here.
External messaging (Kafka, RabbitMQ, Redis) is intentionally deferred
to Phase 8.
"""
from __future__ import annotations

import logging
from typing import Callable, Dict, List, Type

from observation.domain.event_publisher import EventPublisher
from observation.domain.events import DomainEvent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# In-Process publisher (synchronous, in-memory dispatch)
# ---------------------------------------------------------------------------

Handler = Callable[[DomainEvent], None]


class InProcessEventPublisher(EventPublisher):
    """
    Synchronous, in-memory event publisher.

    Handlers are registered per event type and called in registration order.
    Suitable for within-process side-effects (audit log, metrics counters,
    secondary read-model updates, etc.).

    No retries, no persistence, no ordering guarantees across restarts.
    """

    def __init__(self) -> None:
        self._handlers: Dict[Type[DomainEvent], List[Handler]] = {}

    def subscribe(self, event_type: Type[DomainEvent], handler: Handler) -> None:
        """Register a handler for a specific event type."""
        self._handlers.setdefault(event_type, []).append(handler)

    def publish(self, event: DomainEvent) -> None:
        """Dispatch the event to all registered handlers synchronously."""
        handlers = self._handlers.get(type(event), [])
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "InProcessEventPublisher: handler %s raised for event %s",
                    handler,
                    event,
                )
                # Do not propagate — one failing handler must not block others.


# ---------------------------------------------------------------------------
# Logging publisher (structured log output)
# ---------------------------------------------------------------------------

class LoggingEventPublisher(EventPublisher):
    """
    Writes every domain event to the Python logging system.

    Useful as a secondary publisher composed with InProcessEventPublisher,
    or standalone during development.  Structured fields are logged so that
    a log aggregator (e.g. CloudWatch, Loki) can parse them.
    """

    def __init__(
        self,
        log_level: int = logging.INFO,
        event_logger: logging.Logger | None = None,
    ) -> None:
        self._level = log_level
        self._logger = event_logger or logging.getLogger("observation.events")

    def publish(self, event: DomainEvent) -> None:
        self._logger.log(
            self._level,
            "DomainEvent published",
            extra={
                "event_type": event.event_type,
                "event_class": type(event).__name__,
                "event_data": vars(event),
            },
        )


# ---------------------------------------------------------------------------
# Composite publisher (fan-out to multiple publishers)
# ---------------------------------------------------------------------------

class CompositeEventPublisher(EventPublisher):
    """
    Fan-out publisher: publishes to all child publishers in order.
    Errors in one publisher do not prevent others from receiving the event.
    """

    def __init__(self, *publishers: EventPublisher) -> None:
        self._publishers = list(publishers)

    def publish(self, event: DomainEvent) -> None:
        for pub in self._publishers:
            try:
                pub.publish(event)
            except Exception:
                logger.exception(
                    "CompositeEventPublisher: publisher %s raised for event %s",
                    pub,
                    event,
                )
