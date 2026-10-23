"""
Publisher abstraction. No message brokers, queues, or workers are
implemented in this layer — only a simple interface that a future
integration point can adapt to whatever transport it needs.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, List


class EventPublisher(ABC):
    """Abstract publisher. Implementations decide where events go."""

    @abstractmethod
    def publish(self, event: Any) -> None:
        raise NotImplementedError


class InMemoryEventPublisher(EventPublisher):
    """
    Default, dependency-free publisher used in tests and local runs.
    Stores published events in order and optionally forwards them to
    subscriber callbacks. This is not a message broker — it is a
    trivial in-process fan-out used until this layer is wired into a
    real transport by an integrating system.
    """

    def __init__(self) -> None:
        self._published: List[Any] = []
        self._subscribers: List[Callable[[Any], None]] = []

    def publish(self, event: Any) -> None:
        self._published.append(event)
        for subscriber in self._subscribers:
            subscriber(event)

    def subscribe(self, callback: Callable[[Any], None]) -> None:
        self._subscribers.append(callback)

    @property
    def published_events(self) -> tuple[Any, ...]:
        return tuple(self._published)
