"""
Evidence and Pattern value objects.

KnowledgeEvidence references the immutable Observation objects (produced by
the upstream Observation layer) that support a piece of knowledge. This
module does NOT depend on the Observation layer's implementation; it only
depends on identifiers and primitive fields passed in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Tuple

from phase8_learning.domain.enums import EvidenceStrength, PatternType


@dataclass(frozen=True)
class KnowledgeEvidence:
    observation_id: str
    strength: EvidenceStrength
    attributes: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.observation_id:
            raise ValueError("observation_id is required")
        # Freeze the attributes mapping into a sorted, immutable tuple-backed
        # structure to guarantee determinism and immutability.
        object.__setattr__(self, "attributes", dict(sorted(self.attributes.items())))

    def as_dict(self) -> dict:
        return {
            "observation_id": self.observation_id,
            "strength": self.strength.value,
            "attributes": dict(sorted(self.attributes.items())),
        }


@dataclass(frozen=True)
class KnowledgePattern:
    pattern_type: PatternType
    description: str
    signature: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.description:
            raise ValueError("description is required")
        object.__setattr__(self, "signature", dict(sorted(self.signature.items())))

    def as_dict(self) -> dict:
        return {
            "pattern_type": self.pattern_type.value,
            "description": self.description,
            "signature": dict(sorted(self.signature.items())),
        }


@dataclass(frozen=True)
class KnowledgeConfidence:
    """
    Confidence score for a piece of knowledge, in the closed interval [0, 1],
    together with the deterministic inputs that produced it.
    """

    score: float
    sample_size: int
    consistency: float
    components: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (0.0 <= self.score <= 1.0):
            raise ValueError("score must be within [0, 1]")
        if self.sample_size < 0:
            raise ValueError("sample_size must be >= 0")
        if not (0.0 <= self.consistency <= 1.0):
            raise ValueError("consistency must be within [0, 1]")
        object.__setattr__(self, "components", dict(sorted(self.components.items())))

    def as_dict(self) -> dict:
        return {
            "score": self.score,
            "sample_size": self.sample_size,
            "consistency": self.consistency,
            "components": dict(sorted(self.components.items())),
        }
