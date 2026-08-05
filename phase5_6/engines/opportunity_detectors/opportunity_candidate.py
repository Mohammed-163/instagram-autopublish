from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Optional, Tuple


@dataclass(frozen=True)
class Evidence:
    """Evidence backing an opportunity. An opportunity without evidence is invalid."""
    sample_size: int = 0
    categories: Tuple[str, ...] = ()
    hook_fingerprints: Tuple[str, ...] = ()
    features: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    time_period_days: int = 30
    confidence_sources: Tuple[str, ...] = ()
    raw_data: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def is_valid(self) -> bool:
        """An opportunity without evidence is invalid."""
        return self.sample_size > 0 or bool(self.raw_data)


@dataclass(frozen=True)
class Explainability:
    """Structured multi-reason explanation for why an opportunity was detected."""
    reasons: Tuple[str, ...] = ()
    method: str = ""
    detector_logic: str = ""
    thresholds_used: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    evidence: Optional[Evidence] = None
    versions: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "reasons": list(self.reasons),
            "method": self.method,
            "detector_logic": self.detector_logic,
            "thresholds_used": dict(self.thresholds_used),
            "evidence": dict(self.evidence.__dict__) if self.evidence else {},
            "versions": dict(self.versions),
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class OpportunityCandidate:
    """Domain Model for an opportunity candidate returned by a Detector."""
    detector_name: str
    opportunity_type: str
    explainability: Explainability
    related_entities: Tuple[str, ...] = ()
    parent_opportunity_id: Optional[str] = None
    
    fingerprint: str = ""
    structural_fingerprint: str = ""
    feature_fingerprint: str = ""
    fingerprint_hash: str = ""
    
    confidence: float = 0.0
    impact: float = 0.0
    novelty: float = 0.0
    knowledge_gap: float = 0.0
    expected_gain: float = 0.0
    
    opportunity_score: Optional[float] = None
    risk: Optional[float] = None
    
    detector_version: str = "1.0.0"
    knowledge_version: str = ""
    coverage_version: str = ""
    scoring_version: str = ""
    settings_version: str = ""
    fingerprint_version: str = "1.0.0"
    
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def is_valid(self) -> bool:
        return self.explainability.evidence is not None and self.explainability.evidence.is_valid()
