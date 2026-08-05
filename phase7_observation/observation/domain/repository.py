"""
Repository port (abstract interface) for the Observation domain.
Infrastructure adapters implement this; domain never imports infrastructure.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from observation.domain.models import Observation, ObservationFingerprint


class ObservationRepository(ABC):
    """Abstract repository — persistence-ignorant domain port."""

    @abstractmethod
    def save(self, observation: Observation) -> None:
        """Persist a new observation.  Raises if fingerprint already exists."""
        ...

    @abstractmethod
    def find_by_id(self, observation_id: UUID) -> Optional[Observation]:
        """Return an Observation by primary key, or None."""
        ...

    @abstractmethod
    def find_by_fingerprint(
        self, fingerprint: ObservationFingerprint
    ) -> Optional[Observation]:
        """Return an existing Observation matching this fingerprint, or None."""
        ...

    @abstractmethod
    def update(self, observation: Observation) -> None:
        """Persist changes to an existing Observation."""
        ...
