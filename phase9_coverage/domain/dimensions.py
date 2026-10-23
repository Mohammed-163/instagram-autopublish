"""
Coverage dimension value objects.

Exactly eight dimensions are evaluated by this layer. No business
thresholds are hardcoded here — a dimension only carries the measured
score, the raw signal counts that produced it, and a free-text reason.
Any threshold-like decision belongs to the Service layer, driven by
Settings/config, never to these immutable structures.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class DimensionName(str, Enum):
    TOPIC_COVERAGE = "topic_coverage"
    CATEGORY_COVERAGE = "category_coverage"
    EVIDENCE_COVERAGE = "evidence_coverage"
    CONFIDENCE_COVERAGE = "confidence_coverage"
    FRESHNESS_COVERAGE = "freshness_coverage"
    DIVERSITY_COVERAGE = "diversity_coverage"
    KNOWLEDGE_DENSITY = "knowledge_density"
    RELATIONSHIP_COVERAGE = "relationship_coverage"


@dataclass(frozen=True)
class CoverageDimension:
    """A single measured coverage dimension."""

    name: DimensionName
    score: float
    signals: Mapping[str, float] = field(default_factory=dict)
    reason: str = ""

    def __post_init__(self) -> None:
        if not (0.0 <= self.score <= 1.0):
            raise ValueError(
                f"Dimension '{self.name}' score must be within [0.0, 1.0], got {self.score}"
            )


@dataclass(frozen=True)
class CoverageDimensionSet:
    """An immutable, ordered collection of all evaluated dimensions."""

    dimensions: tuple[CoverageDimension, ...]

    def __post_init__(self) -> None:
        names = [d.name for d in self.dimensions]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate dimension names are not allowed in a CoverageDimensionSet")

    def as_sorted_tuple(self) -> tuple[CoverageDimension, ...]:
        """Deterministic ordering by dimension name, used for fingerprinting/serialization."""
        return tuple(sorted(self.dimensions, key=lambda d: d.name.value))

    def get(self, name: DimensionName) -> CoverageDimension | None:
        for dimension in self.dimensions:
            if dimension.name == name:
                return dimension
        return None

    def average_score(self) -> float:
        if not self.dimensions:
            return 0.0
        return sum(d.score for d in self.dimensions) / len(self.dimensions)
