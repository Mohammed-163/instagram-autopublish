"""
Event publisher abstraction. Engines and services depend only on the
EventPublisher interface, never on a concrete transport, so this module
can later be backed by any broker without touching business logic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Callable, Dict, List

from .domain_events import DomainEvent

EventSubscriber = Callable[[DomainEvent], None]


class EventPublisher(ABC):
    """Abstract publisher interface."""

    @abstractmethod
    def publish(self, event: DomainEvent) -> None:
        raise NotImplementedError

    @abstractmethod
    def subscribe(self, event_type: str, subscriber: EventSubscriber) -> None:
        raise NotImplementedError


class InMemoryEventPublisher(EventPublisher):
    """
    Deterministic, in-process publisher. Suitable for this standalone
    module since no external message broker is in scope.
    """

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[EventSubscriber]] = defaultdict(list)
        self._history: List[DomainEvent] = []

    def publish(self, event: DomainEvent) -> None:
        self._history.append(event)
        for subscriber in self._subscribers.get(event.event_type, []):
            subscriber(event)
        for subscriber in self._subscribers.get("*", []):
            subscriber(event)

    def subscribe(self, event_type: str, subscriber: EventSubscriber) -> None:
        self._subscribers[event_type].append(subscriber)

    @property
    def history(self) -> List[DomainEvent]:
        return list(self._history)
