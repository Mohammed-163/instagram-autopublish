"""
DecisionCandidate
==================
Phase 5 (Part 1) — Decision Layer Foundation.

Immutable domain model representing a candidate decision derived from a
completed weekly strategy. Mirrors the shape/conventions already used by
`engines.opportunity_detectors.opportunity_candidate.OpportunityCandidate`
so the Decision Layer stays architecturally consistent with the existing
Opportunity Layer, without importing from it (kept self-contained on
purpose — this is a foundation module).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Optional, Tuple


@dataclass(frozen=True)
class DecisionEvidence:
    """Evidence backing a decision candidate. Traces back to the strategy
    candidate(s) and opportunities that justified it."""

    strategy_version_id: str = ""
    strategy_candidate_id: str = ""
    category: str = ""
    topic: str = ""
    hook_type: str = ""
    is_experiment: bool = False
    source_confidence: float = 0.0
    source_expected_success: float = 0.0
    raw: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def is_valid(self) -> bool:
        return bool(self.strategy_candidate_id) and bool(self.strategy_version_id)


@dataclass(frozen=True)
class DecisionExplainability:
    """Structured multi-reason explanation for why a decision was proposed."""

    reasons: Tuple[str, ...] = ()
    method: str = ""
    evidence: Optional[DecisionEvidence] = None
    thresholds_used: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "reasons": list(self.reasons),
            "method": self.method,
            "evidence": dict(self.evidence.__dict__) if self.evidence else {},
            "thresholds_used": dict(self.thresholds_used),
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class DecisionCandidate:
    """Domain model for a candidate decision produced by Phase5DecisionEngine.

    Immutable by design (frozen dataclass): once built, an engine or service
    must produce a *new* instance (e.g. via `dataclasses.replace`) rather than
    mutate this one — this keeps scoring/fingerprinting side-effect free and
    replayable.
    """

    decision_type: str
    objective_profile: str
    explainability: DecisionExplainability

    related_opportunities: Tuple[str, ...] = ()

    confidence: float = 0.0
    expected_gain: float = 0.0
    risk: Optional[float] = None
    decision_score: Optional[float] = None

    # Version bookkeeping — every version that contributed to this candidate,
    # so a decision can always be traced back to the exact settings/knowledge
    # state that produced it.
    versions: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    scoring_version: str = ""

    # Fingerprint fields — deduplication identity. Populated exclusively by
    # Phase5DecisionService; never computed by the engine.
    fingerprint: str = ""
    structural_fingerprint: str = ""
    feature_fingerprint: str = ""
    fingerprint_hash: str = ""
    fingerprint_version: str = "1.0.0"

    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def is_valid(self) -> bool:
        return bool(self.decision_type) and bool(self.objective_profile) and self.explainability is not None
