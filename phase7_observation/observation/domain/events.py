"""
Domain events for the Observation bounded context.
All events are immutable value objects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict
from uuid import UUID


@dataclass(frozen=True)
class DomainEvent:
    """Base for all domain events."""
    event_type: str


@dataclass(frozen=True)
class ExecutionCompleted(DomainEvent):
    """
    Inbound event that triggers observation recording.
    Produced by the Execution bounded context; consumed here.
    """
    execution_id: str
    workflow_id: str
    node_id: str
    tenant_id: str
    payload: Dict[str, Any]
    event_type: str = field(default="execution.completed", init=False)

    def __post_init__(self) -> None:
        # frozen=True means we use object.__setattr__ for derived fields
        object.__setattr__(self, "event_type", "execution.completed")


@dataclass(frozen=True)
class ObservationRecorded(DomainEvent):
    """Published after a new observation is successfully persisted."""
    observation_id: UUID
    fingerprint: str
    tenant_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    event_type: str = field(default="observation.recorded", init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_type", "observation.recorded")


@dataclass(frozen=True)
class ObservationDuplicated(DomainEvent):
    """Published when an observation fingerprint already exists."""
    fingerprint: str
    tenant_id: str
    event_type: str = field(default="observation.duplicated", init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_type", "observation.duplicated")
