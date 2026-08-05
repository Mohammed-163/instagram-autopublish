"""
Shared Event Bus.

The single event bus for the entire autonomous AI system.
All phases publish and subscribe through this bus.

Architecture:
  Phase5/6 (Strategy/Decision/Execution)
       |  DecisionCandidateApproved
       v
  Phase6 (Execution Engine)
       |  ExecutionCompleted
       v
  Phase7 (Observation)
       |  ObservationRecorded
       v
  Phase8 (Learning)
       |  KnowledgeValidated
       v
  Phase9 (Knowledge Coverage)
       |  KnowledgeCoverageCalculated
       v
  Phase10 (Intelligence Core)
       |  (feedback events)
       v
  Phase5/6 (feedback loop)

Usage:
    from shared.event_bus import shared_event_bus
    shared_event_bus.subscribe(MyEvent, my_handler)
    shared_event_bus.publish(MyEvent(...))
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger("shared.event_bus")

EventHandler = Callable[[Any], None]


class SharedEventBus:
    """
    Unified in-process event bus for inter-phase communication.

    Supports two subscription modes:
      - Type-based (for Phase5/6 DomainEvent subclasses)
      - String-based (for Phase10's string event_type pattern)
    """

    def __init__(self) -> None:
        self._type_subscribers: Dict[Type, List[EventHandler]] = defaultdict(list)
        self._string_subscribers: Dict[str, List[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: Type | str, handler: EventHandler) -> None:
        """Subscribe to an event type (class or string name)."""
        if isinstance(event_type, str):
            self._string_subscribers[event_type].append(handler)
        else:
            self._type_subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: Type | str, handler: EventHandler) -> None:
        if isinstance(event_type, str):
            subscribers = self._string_subscribers.get(event_type, [])
        else:
            subscribers = self._type_subscribers.get(event_type, [])
        if handler in subscribers:
            subscribers.remove(handler)

    def publish(self, event: Any) -> None:
        """Dispatch the event to all registered handlers."""
        # Type-based dispatch (Phase5/6 style)
        for handler in self._type_subscribers.get(type(event), []):
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "Handler %r failed for event type %s", handler, type(event).__name__
                )

        # String-based dispatch (Phase10 style — event has .event_type attribute)
        event_type_str: Optional[str] = getattr(event, "event_type", None)
        if event_type_str:
            for handler in self._string_subscribers.get(event_type_str, []):
                try:
                    handler(event)
                except Exception:
                    logger.exception(
                        "Handler %r failed for event_type '%s'", handler, event_type_str
                    )
            # Wildcard subscribers
            for handler in self._string_subscribers.get("*", []):
                try:
                    handler(event)
                except Exception:
                    logger.exception(
                        "Wildcard handler %r failed for event_type '%s'", handler, event_type_str
                    )


# Process-wide singleton shared across all phases
shared_event_bus = SharedEventBus()
