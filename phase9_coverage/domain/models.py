"""
Core immutable domain models for the Knowledge Coverage Layer.

All dataclasses here are frozen. Nothing in this module computes a
fingerprint — that is the exclusive responsibility of
`domain/fingerprint.py`. Nothing here talks to a database, a repository,
or an event bus.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping, Sequence

from phase9_coverage.domain.dimensions import CoverageDimensionSet
from phase9_coverage.domain.gaps import CoverageGapSet


@dataclass(frozen=True)
class CoverageProfile:
    """
    Describes *how* coverage was evaluated for a piece of knowledge:
    which profile/policy of dimension weighting and evaluation rules
    was in effect. This is a label + metadata carrier, not a scorer.
    """

    profile_id: str
    profile_name: str
    description: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CoverageEvidence:
    """
    The raw evidentiary inputs/outputs behind a coverage calculation.
    Kept separate from KnowledgeCoverage so the "why" can be inspected,
    stored, or pruned independently of the coverage result itself.
    """

    knowledge_versions: tuple[str, ...]
    knowledge_statistics: Mapping[str, float]
    coverage_inputs: Mapping[str, str]
    coverage_outputs: Mapping[str, str]


@dataclass(frozen=True)
class CoverageExplainability:
    """Human-readable explanation of how a coverage result was reached."""

    coverage_method: str
    coverage_reason: str
    dimensions_evaluated: tuple[str, ...]
    gaps_detected: tuple[str, ...]
    confidence_reason: str
    versions: Mapping[str, str]


@dataclass(frozen=True)
class KnowledgeCoverage:
    """
    The top-level result of evaluating coverage for a single piece of
    validated knowledge. Immutable, deterministic (aside from
    created_at/coverage_id which are identity/audit fields, not part
    of the fingerprint).
    """

    coverage_id: str
    knowledge_id: str
    coverage_profile: CoverageProfile
    coverage_score: float
    coverage_dimensions: CoverageDimensionSet
    detected_gaps: CoverageGapSet
    coverage_confidence: float
    fingerprint: str
    structural_fingerprint: str
    feature_fingerprint: str
    fingerprint_hash: str
    fingerprint_version: str
    engine_version: str
    schema_version: str
    created_at: datetime
    versions: Mapping[str, str]
    explainability: CoverageExplainability

    def __post_init__(self) -> None:
        if not (0.0 <= self.coverage_score <= 1.0):
            raise ValueError("coverage_score must be within [0.0, 1.0]")
        if not (0.0 <= self.coverage_confidence <= 1.0):
            raise ValueError("coverage_confidence must be within [0.0, 1.0]")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")


def utc_now() -> datetime:
    """Single point of truth for 'now' generation, kept out of fingerprinting."""
    return datetime.now(timezone.utc)
