"""
Event publisher abstraction.

Only interfaces plus a simple in-process implementation are provided, per
specification. No Kafka, RabbitMQ, or Redis integration.
"""

from __future__ import annotations

import abc
from typing import Any, Callable, DefaultDict, List
from collections import defaultdict


class EventPublisher(abc.ABC):
    """Abstract publisher interface."""

    @abc.abstractmethod
    def publish(self, event: Any) -> None:
        raise NotImplementedError


class InProcessEventPublisher(EventPublisher):
    """
    A simple, synchronous, in-process publisher.

    Subscribers are registered per event type (class). Publishing an event
    invokes all subscribers registered for that exact event type, in the
    deterministic order they were registered.
    """

    def __init__(self) -> None:
        self._subscribers: DefaultDict[type, List[Callable[[Any], None]]] = defaultdict(list)
        self._published: List[Any] = []

    def subscribe(self, event_type: type, handler: Callable[[Any], None]) -> None:
        self._subscribers[event_type].append(handler)

    def publish(self, event: Any) -> None:
        self._published.append(event)
        for handler in self._subscribers.get(type(event), []):
            handler(event)

    @property
    def published_events(self) -> List[Any]:
        """Read-only view of everything published so far (useful for tests)."""
        return list(self._published)


class NullEventPublisher(EventPublisher):
    """A publisher that discards all events. Useful for tests or dry runs."""

    def publish(self, event: Any) -> None:
        return None
