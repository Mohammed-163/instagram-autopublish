"""
KnowledgeExplainability value object.

Every KnowledgeCandidate must carry an explainability record describing why
it was formed, in fully deterministic and auditable form.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Tuple

from phase8_learning.domain.evidence import KnowledgeConfidence, KnowledgeEvidence
from phase8_learning.domain.versioning import KnowledgeVersion


@dataclass(frozen=True)
class KnowledgeExplainability:
    reason: str
    source_observations: Tuple[str, ...]
    confidence: KnowledgeConfidence
    supporting_evidence: Tuple[KnowledgeEvidence, ...]
    versions: KnowledgeVersion
    thresholds_used: Mapping[str, float]
    algorithm: str

    def __post_init__(self) -> None:
        if not self.reason:
            raise ValueError("reason is required")
        if not self.source_observations:
            raise ValueError("source_observations must not be empty")
        if not self.algorithm:
            raise ValueError("algorithm is required")

        object.__setattr__(
            self, "source_observations", tuple(sorted(self.source_observations))
        )
        object.__setattr__(
            self,
            "supporting_evidence",
            tuple(
                sorted(self.supporting_evidence, key=lambda e: e.observation_id)
            ),
        )
        object.__setattr__(
            self, "thresholds_used", dict(sorted(self.thresholds_used.items()))
        )

    def as_dict(self) -> dict:
        return {
            "reason": self.reason,
            "source_observations": list(self.source_observations),
            "confidence": self.confidence.as_dict(),
            "supporting_evidence": [e.as_dict() for e in self.supporting_evidence],
            "versions": self.versions.as_dict(),
            "thresholds_used": dict(sorted(self.thresholds_used.items())),
            "algorithm": self.algorithm,
        }
