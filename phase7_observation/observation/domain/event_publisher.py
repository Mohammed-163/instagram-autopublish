"""
Event publisher port.  Concrete implementations live in infrastructure.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from observation.domain.events import DomainEvent


class EventPublisher(ABC):
    """Abstract port for publishing domain events."""

    @abstractmethod
    def publish(self, event: DomainEvent) -> None:
        """Publish a single domain event."""
        ...
