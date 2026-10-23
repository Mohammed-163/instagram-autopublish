"""
KnowledgeFingerprint value object and deterministic fingerprint generation.

Rules (per specification):
    - Deterministic: same logical input always produces the same fingerprint.
    - SHA-256 is used for hashing.
    - Dictionary keys are always sorted before hashing.
    - Never use timestamps.
    - Never use UUIDs.
    - Never use random values.

Only LearningService is permitted to construct fingerprints in the
application flow (enforced by convention / code review, not by this module
itself, since the domain layer must stay framework and caller agnostic).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping


def _canonical_json(payload: Mapping[str, Any]) -> str:
    """
    Produce a canonical, deterministic JSON string for a mapping.

    - Keys are sorted recursively.
    - No whitespace ambiguity (fixed separators).
    - No non-deterministic float representation surprises are introduced
      beyond what json.dumps already guarantees for a given input.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def compute_structural_fingerprint(structural_payload: Mapping[str, Any]) -> str:
    """
    Fingerprint derived purely from the *structure* of the knowledge
    (e.g. pattern type, shape of the evidence set, ordered key names).
    """
    canonical = _canonical_json(structural_payload)
    return sha256_hex(canonical)


def compute_feature_fingerprint(feature_payload: Mapping[str, Any]) -> str:
    """
    Fingerprint derived from the *feature values* of the knowledge
    (e.g. normalized numeric feature buckets, categorical feature values).
    """
    canonical = _canonical_json(feature_payload)
    return sha256_hex(canonical)


def compute_fingerprint_hash(structural_fingerprint: str, feature_fingerprint: str) -> str:
    """
    Combined fingerprint hash used for deduplication and lookup.
    """
    combined = _canonical_json(
        {
            "structural_fingerprint": structural_fingerprint,
            "feature_fingerprint": feature_fingerprint,
        }
    )
    return sha256_hex(combined)


@dataclass(frozen=True)
class KnowledgeFingerprint:
    structural_fingerprint: str
    feature_fingerprint: str
    fingerprint_hash: str

    def __post_init__(self) -> None:
        for field_name in ("structural_fingerprint", "feature_fingerprint", "fingerprint_hash"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or len(value) != 64:
                raise ValueError(f"{field_name} must be a 64-character SHA-256 hex digest")

    @staticmethod
    def build(
        structural_payload: Mapping[str, Any],
        feature_payload: Mapping[str, Any],
    ) -> "KnowledgeFingerprint":
        structural_fp = compute_structural_fingerprint(structural_payload)
        feature_fp = compute_feature_fingerprint(feature_payload)
        combined = compute_fingerprint_hash(structural_fp, feature_fp)
        return KnowledgeFingerprint(
            structural_fingerprint=structural_fp,
            feature_fingerprint=feature_fp,
            fingerprint_hash=combined,
        )

    def as_dict(self) -> dict:
        return {
            "structural_fingerprint": self.structural_fingerprint,
            "feature_fingerprint": self.feature_fingerprint,
            "fingerprint_hash": self.fingerprint_hash,
        }
