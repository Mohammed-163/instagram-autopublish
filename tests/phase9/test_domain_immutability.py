from __future__ import annotations

import dataclasses

import pytest

from phase9_coverage.domain.dimensions import CoverageDimension, DimensionName
from phase9_coverage.domain.gaps import CoverageGap, GapSeverity, GapType
from phase9_coverage.domain.models import CoverageEvidence, CoverageExplainability, CoverageProfile


def test_coverage_dimension_is_frozen():
    dim = CoverageDimension(name=DimensionName.TOPIC_COVERAGE, score=0.5)
    with pytest.raises(dataclasses.FrozenInstanceError):
        dim.score = 0.9  # type: ignore[misc]


def test_coverage_gap_is_frozen():
    gap = CoverageGap(
        gap_type=GapType.MISSING_TOPIC,
        severity=GapSeverity.HIGH,
        description="x",
        related_dimension=DimensionName.TOPIC_COVERAGE.value,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        gap.description = "y"  # type: ignore[misc]


def test_coverage_profile_is_frozen():
    profile = CoverageProfile(profile_id="p1", profile_name="Profile 1")
    with pytest.raises(dataclasses.FrozenInstanceError):
        profile.profile_name = "changed"  # type: ignore[misc]


def test_coverage_evidence_is_frozen():
    evidence = CoverageEvidence(
        knowledge_versions=("v1",),
        knowledge_statistics={},
        coverage_inputs={},
        coverage_outputs={},
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        evidence.knowledge_versions = ("v2",)  # type: ignore[misc]


def test_coverage_explainability_is_frozen():
    explainability = CoverageExplainability(
        coverage_method="m",
        coverage_reason="r",
        dimensions_evaluated=(),
        gaps_detected=(),
        confidence_reason="c",
        versions={},
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        explainability.coverage_method = "changed"  # type: ignore[misc]


def test_dimension_score_out_of_range_rejected():
    with pytest.raises(ValueError):
        CoverageDimension(name=DimensionName.TOPIC_COVERAGE, score=1.5)
