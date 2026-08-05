"""
Outbound events published by the Knowledge Coverage Layer.

These are the only three event types this layer emits. They carry
coverage *results*, never opportunities, decisions, or executions.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from phase9_coverage.domain.models import KnowledgeCoverage


@dataclass(frozen=True)
class KnowledgeCoverageCalculated:
    """Emitted whenever a full coverage evaluation completes."""

    coverage: KnowledgeCoverage
    occurred_at: datetime


@dataclass(frozen=True)
class CoverageGapDetected:
    """
    Emitted once per coverage evaluation that has one or more gaps,
    summarizing the gaps found. Detail lives on `coverage.detected_gaps`.
    """

    coverage_id: str
    knowledge_id: str
    gap_count: int
    occurred_at: datetime


@dataclass(frozen=True)
class CoverageUpdated:
    """
    Emitted when a new coverage evaluation supersedes a prior one for
    the same knowledge_id (i.e. a transition, not a first-time result).
    """

    coverage_id: str
    knowledge_id: str
    previous_coverage_id: str
    previous_score: float
    new_score: float
    occurred_at: datetime
