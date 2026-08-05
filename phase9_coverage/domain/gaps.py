"""
Coverage gap value objects.

Gaps are *reported*, never acted upon here. This layer never creates
opportunities from gaps — that is the responsibility of a downstream
layer (Opportunity Discovery), which is explicitly out of scope.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class GapType(str, Enum):
    MISSING_TOPIC = "missing_topic"
    WEAK_EVIDENCE = "weak_evidence"
    LOW_CONFIDENCE = "low_confidence"
    OUTDATED_KNOWLEDGE = "outdated_knowledge"
    IMBALANCED_CATEGORY = "imbalanced_category"
    INSUFFICIENT_DIVERSITY = "insufficient_diversity"
    SPARSE_RELATIONSHIP = "sparse_relationship"
    LOW_DENSITY = "low_density"


class GapSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class CoverageGap:
    """A single detected coverage gap. Detection only — no remediation."""

    gap_type: GapType
    severity: GapSeverity
    description: str
    related_dimension: str
    details: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CoverageGapSet:
    """An immutable, deterministic collection of detected gaps."""

    gaps: tuple[CoverageGap, ...]

    def as_sorted_tuple(self) -> tuple[CoverageGap, ...]:
        return tuple(
            sorted(
                self.gaps,
                key=lambda g: (g.gap_type.value, g.severity.value, g.related_dimension),
            )
        )

    def is_empty(self) -> bool:
        return len(self.gaps) == 0

    def count_by_severity(self, severity: GapSeverity) -> int:
        return sum(1 for g in self.gaps if g.severity == severity)
