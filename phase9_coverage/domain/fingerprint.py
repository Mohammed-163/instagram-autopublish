"""
The ONLY place in this codebase allowed to generate fingerprints.

Rules enforced here:
  - SHA-256 only.
  - json.dumps(..., sort_keys=True) for all serialization prior to hashing.
  - Fully deterministic: no timestamps, no randomness, no UUIDs feed
    into the hashed payload.
  - Same logical input -> same fingerprint, forever, across processes.

No other module (service, engine, repository, application) may compute
a hash of coverage content and call it a fingerprint. They must call
into this module.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from phase9_coverage.domain.dimensions import CoverageDimensionSet
from phase9_coverage.domain.gaps import CoverageGapSet


def _sha256_hex(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _dimensions_payload(dimensions: CoverageDimensionSet) -> list[dict[str, Any]]:
    ordered = dimensions.as_sorted_tuple()
    return [
        {
            "name": d.name.value,
            "score": round(d.score, 6),
            "signals": dict(sorted(d.signals.items())),
        }
        for d in ordered
    ]


def _gaps_payload(gaps: CoverageGapSet) -> list[dict[str, Any]]:
    ordered = gaps.as_sorted_tuple()
    return [
        {
            "gap_type": g.gap_type.value,
            "severity": g.severity.value,
            "related_dimension": g.related_dimension,
            "details": dict(sorted(g.details.items())),
        }
        for g in ordered
    ]


def compute_structural_fingerprint(
    *,
    knowledge_id: str,
    knowledge_versions: Sequence[str],
    coverage_profile_id: str,
) -> str:
    """
    Fingerprints the *structural identity* of what is being covered:
    which knowledge, which versions of it, under which coverage profile.
    Deliberately excludes computed scores so structural identity is
    stable even if scoring logic evolves.
    """
    payload = {
        "knowledge_id": knowledge_id,
        "knowledge_versions": sorted(knowledge_versions),
        "coverage_profile_id": coverage_profile_id,
    }
    return _sha256_hex(payload)


def compute_feature_fingerprint(
    *,
    coverage_dimensions: CoverageDimensionSet,
    detected_gaps: CoverageGapSet,
) -> str:
    """
    Fingerprints the *measured features*: dimension scores/signals and
    detected gaps. Two evaluations with identical measured features
    produce an identical feature fingerprint, regardless of order of
    computation.
    """
    payload = {
        "dimensions": _dimensions_payload(coverage_dimensions),
        "gaps": _gaps_payload(detected_gaps),
    }
    return _sha256_hex(payload)


def compute_fingerprint_hash(
    *,
    structural_fingerprint: str,
    feature_fingerprint: str,
    fingerprint_version: str,
) -> str:
    """
    Combines structural + feature fingerprints plus the fingerprinting
    algorithm's own version into one top-level hash used for
    deduplication lookups.
    """
    payload = {
        "structural_fingerprint": structural_fingerprint,
        "feature_fingerprint": feature_fingerprint,
        "fingerprint_version": fingerprint_version,
    }
    return _sha256_hex(payload)


def compute_all_fingerprints(
    *,
    knowledge_id: str,
    knowledge_versions: Sequence[str],
    coverage_profile_id: str,
    coverage_dimensions: CoverageDimensionSet,
    detected_gaps: CoverageGapSet,
    fingerprint_version: str,
) -> tuple[str, str, str]:
    """Convenience wrapper returning (structural, feature, hash)."""
    structural = compute_structural_fingerprint(
        knowledge_id=knowledge_id,
        knowledge_versions=knowledge_versions,
        coverage_profile_id=coverage_profile_id,
    )
    feature = compute_feature_fingerprint(
        coverage_dimensions=coverage_dimensions,
        detected_gaps=detected_gaps,
    )
    fingerprint_hash = compute_fingerprint_hash(
        structural_fingerprint=structural,
        feature_fingerprint=feature,
        fingerprint_version=fingerprint_version,
    )
    return structural, feature, fingerprint_hash
