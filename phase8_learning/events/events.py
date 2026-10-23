"""
Event definitions for the Learning Layer.

Inbound event:
    ObservationRecorded - the only event this layer consumes. It is
    produced upstream by the Observation layer. This module only declares
    the minimal shape the Learning Layer depends on; it does not import
    anything from an Observation layer implementation, keeping this
    project fully standalone.

Outbound events (published by LearningService):
    KnowledgeCandidateCreated
    KnowledgeValidated
    KnowledgeStored
    KnowledgeVersionCreated
    KnowledgeUpdated
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Tuple


@dataclass(frozen=True)
class ObservationRecorded:
    """
    Inbound event representing a single immutable Observation produced by
    the upstream Observation layer.

    Fields are intentionally primitive/generic so that this layer never
    depends on the upstream Observation domain model directly.
    """

    observation_id: str
    subject_id: str
    metric_name: str
    metric_value: float
    context: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.observation_id:
            raise ValueError("observation_id is required")
        if not self.subject_id:
            raise ValueError("subject_id is required")
        if not self.metric_name:
            raise ValueError("metric_name is required")
        object.__setattr__(self, "context", dict(sorted(self.context.items())))


@dataclass(frozen=True)
class KnowledgeCandidateCreated:
    candidate_title: str
    source_observations: Tuple[str, ...]
    fingerprint_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "source_observations", tuple(sorted(self.source_observations))
        )


@dataclass(frozen=True)
class KnowledgeValidated:
    knowledge_id: str
    fingerprint_hash: str


@dataclass(frozen=True)
class KnowledgeStored:
    knowledge_id: str
    fingerprint_hash: str
    knowledge_version: int


@dataclass(frozen=True)
class KnowledgeVersionCreated:
    knowledge_id: str
    previous_knowledge_id: str
    knowledge_version: int


@dataclass(frozen=True)
class KnowledgeUpdated:
    knowledge_id: str
    status: str
