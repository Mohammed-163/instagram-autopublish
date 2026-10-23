"""
Inbound event contract(s) consumed by this layer.

KnowledgeValidated is produced upstream by the Learning Layer. This
layer does not own or validate its schema beyond what it needs to
consume — it only depends on the fields it actually uses.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence


@dataclass(frozen=True)
class KnowledgeValidated:
    """
    Represents a validated Knowledge object handed off from the
    Learning Layer. This layer treats it as a read-only input.
    """

    knowledge_id: str
    knowledge_versions: tuple[str, ...]
    topics: tuple[str, ...]
    categories: tuple[str, ...]
    evidence_count: int
    confidence_scores: tuple[float, ...]
    freshness_timestamps: tuple[str, ...]
    relationships: tuple[str, ...]
    statistics: Mapping[str, float] = field(default_factory=dict)
