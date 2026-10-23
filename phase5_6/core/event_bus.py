"""
Event Bus.

Services must never call each other directly (`metrics_service.x()` from
inside `post_service.y()`). Instead a service *publishes* a DomainEvent and
whoever cares *subscribes* to that event type. This is what makes it
possible to plug a brand-new engine into the pipeline later without editing
any of the existing services:

    Post Published -> Event -> Metrics -> Knowledge -> Notification -> ...

Usage
-----
    from core.event_bus import event_bus
    from core.events import PostPublished

    event_bus.subscribe(PostPublished, metrics_service.on_post_published)
    event_bus.publish(PostPublished(post_id=post.id))

The bus is deliberately dumb: synchronous, in-process, no retries. It is the
seam future engines plug into — not a message queue.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Callable, Dict, List, Optional, Type

from core.events import DomainEvent

logger = logging.getLogger(__name__)

EventHandler = Callable[[DomainEvent], None]


class EventBus:
    def __init__(self, event_log: Optional["EventLogWriter"] = None) -> None:
        self._subscribers: Dict[Type[DomainEvent], List[EventHandler]] = defaultdict(list)
        # Injected, not imported directly -> keeps the bus testable without a DB.
        self._event_log = event_log

    def subscribe(self, event_type: Type[DomainEvent], handler: EventHandler) -> None:
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: Type[DomainEvent], handler: EventHandler) -> None:
        if handler in self._subscribers.get(event_type, []):
            self._subscribers[event_type].remove(handler)

    def publish(self, event: DomainEvent) -> None:
        self._persist(event)

        handlers = self._subscribers.get(type(event), [])
        for handler in handlers:
            try:
                handler(event)
            except Exception:  # a broken subscriber must never break the publisher
                logger.exception(
                    "Event handler %r failed while handling %s", handler, event.event_type
                )

    def _persist(self, event: DomainEvent) -> None:
        if self._event_log is None:
            return
        try:
            self._event_log.log(
                event_type=event.event_type,
                source=type(event).__module__,
                payload=_json_safe(event.payload()),
            )
        except Exception:
            logger.exception("Failed to persist event %s to the event log", event.event_type)


def _json_safe(value):
    """Convert values such as UUIDs and datetimes to JSON-safe primitives."""
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value) if value.__class__.__module__ == "uuid" else value


class EventLogWriter:
    """Narrow protocol the bus needs from a repository to persist events.
    Satisfied by database.repositories.events_repository as-is."""

    def log(self, event_type: str, source: str, payload: Optional[dict] = None) -> None:  # pragma: no cover
        raise NotImplementedError


def _build_default_event_bus() -> EventBus:
    try:
        from database.repositories import events_repository
        return EventBus(event_log=events_repository)
    except Exception:  # DB layer may be unavailable (e.g. unit tests) -> bus still works in-memory
        return EventBus(event_log=None)


# Process-wide default instance. Services resolve this via core.container
# unless a different bus is injected (e.g. a fake one in tests).
event_bus = _build_default_event_bus()
