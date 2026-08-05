from __future__ import annotations

from phase9_coverage.domain.dimensions import CoverageDimension, CoverageDimensionSet, DimensionName
from phase9_coverage.domain.fingerprint import compute_all_fingerprints
from phase9_coverage.domain.gaps import CoverageGap, CoverageGapSet, GapSeverity, GapType


def _sample_dimensions() -> CoverageDimensionSet:
    return CoverageDimensionSet(
        dimensions=(
            CoverageDimension(name=DimensionName.TOPIC_COVERAGE, score=0.5, signals={"a": 1.0}),
            CoverageDimension(name=DimensionName.EVIDENCE_COVERAGE, score=0.8, signals={"b": 2.0}),
        )
    )


def _sample_gaps() -> CoverageGapSet:
    return CoverageGapSet(
        gaps=(
            CoverageGap(
                gap_type=GapType.WEAK_EVIDENCE,
                severity=GapSeverity.MEDIUM,
                description="weak",
                related_dimension=DimensionName.EVIDENCE_COVERAGE.value,
            ),
        )
    )


def test_fingerprints_are_deterministic_across_calls():
    dims = _sample_dimensions()
    gaps = _sample_gaps()

    first = compute_all_fingerprints(
        knowledge_id="k1",
        knowledge_versions=["v2", "v1"],
        coverage_profile_id="default",
        coverage_dimensions=dims,
        detected_gaps=gaps,
        fingerprint_version="1.0.0",
    )
    second = compute_all_fingerprints(
        knowledge_id="k1",
        knowledge_versions=["v1", "v2"],  # different order, same set
        coverage_profile_id="default",
        coverage_dimensions=dims,
        detected_gaps=gaps,
        fingerprint_version="1.0.0",
    )

    assert first == second


def test_fingerprint_changes_when_scores_change():
    dims_a = _sample_dimensions()
    dims_b = CoverageDimensionSet(
        dimensions=(
            CoverageDimension(name=DimensionName.TOPIC_COVERAGE, score=0.51, signals={"a": 1.0}),
            CoverageDimension(name=DimensionName.EVIDENCE_COVERAGE, score=0.8, signals={"b": 2.0}),
        )
    )
    gaps = _sample_gaps()

    fp_a = compute_all_fingerprints(
        knowledge_id="k1",
        knowledge_versions=["v1"],
        coverage_profile_id="default",
        coverage_dimensions=dims_a,
        detected_gaps=gaps,
        fingerprint_version="1.0.0",
    )
    fp_b = compute_all_fingerprints(
        knowledge_id="k1",
        knowledge_versions=["v1"],
        coverage_profile_id="default",
        coverage_dimensions=dims_b,
        detected_gaps=gaps,
        fingerprint_version="1.0.0",
    )

    assert fp_a[1] != fp_b[1]  # feature fingerprint differs
    assert fp_a[2] != fp_b[2]  # fingerprint_hash differs
    assert fp_a[0] == fp_b[0]  # structural fingerprint unaffected by scores


def test_fingerprint_hash_has_no_timestamp_or_random_dependency():
    dims = _sample_dimensions()
    gaps = _sample_gaps()

    results = {
        compute_all_fingerprints(
            knowledge_id="k1",
            knowledge_versions=["v1"],
            coverage_profile_id="default",
            coverage_dimensions=dims,
            detected_gaps=gaps,
            fingerprint_version="1.0.0",
        )
        for _ in range(5)
    }

    assert len(results) == 1
