"""
Core domain aggregates: KnowledgeCandidate and Knowledge.

KnowledgeCandidate:
    Produced by the LearningEngine. Not yet fingerprinted, not yet
    persisted. Purely an in-memory proposal describing a possible unit
    of reusable knowledge.

Knowledge:
    The persisted, fingerprinted, versioned aggregate produced once a
    LearningService validates and stores a KnowledgeCandidate.

Both are immutable (frozen dataclasses). "Mutation" is always expressed as
producing a new instance (e.g. a new version).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

from phase8_learning.domain.enums import KnowledgeStatus
from phase8_learning.domain.evidence import KnowledgeConfidence, KnowledgeEvidence, KnowledgePattern
from phase8_learning.domain.explainability import KnowledgeExplainability
from phase8_learning.domain.fingerprint import KnowledgeFingerprint
from phase8_learning.domain.versioning import KnowledgeVersion


@dataclass(frozen=True)
class KnowledgeCandidate:
    """
    An unpersisted proposal for a piece of knowledge, produced by the
    LearningEngine and handed to the LearningService for validation,
    fingerprinting, and storage.
    """

    title: str
    pattern: KnowledgePattern
    evidence: Tuple[KnowledgeEvidence, ...]
    confidence: KnowledgeConfidence
    explainability: KnowledgeExplainability
    structural_payload: Mapping[str, str]
    feature_payload: Mapping[str, str]

    def __post_init__(self) -> None:
        if not self.title:
            raise ValueError("title is required")
        if not self.evidence:
            raise ValueError("evidence must not be empty")

        object.__setattr__(
            self, "evidence", tuple(sorted(self.evidence, key=lambda e: e.observation_id))
        )
        object.__setattr__(
            self, "structural_payload", dict(sorted(self.structural_payload.items()))
        )
        object.__setattr__(
            self, "feature_payload", dict(sorted(self.feature_payload.items()))
        )

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "pattern": self.pattern.as_dict(),
            "evidence": [e.as_dict() for e in self.evidence],
            "confidence": self.confidence.as_dict(),
            "explainability": self.explainability.as_dict(),
            "structural_payload": dict(sorted(self.structural_payload.items())),
            "feature_payload": dict(sorted(self.feature_payload.items())),
        }


@dataclass(frozen=True)
class Knowledge:
    """
    The persisted, immutable aggregate representing a durable unit of
    reusable knowledge. Each update to a Knowledge item produces a new
    Knowledge instance with an incremented KnowledgeVersion; the previous
    instance is retained (as history) by the repository layer.
    """

    knowledge_id: str
    title: str
    status: KnowledgeStatus
    pattern: KnowledgePattern
    evidence: Tuple[KnowledgeEvidence, ...]
    confidence: KnowledgeConfidence
    explainability: KnowledgeExplainability
    fingerprint: KnowledgeFingerprint
    version: KnowledgeVersion
    previous_knowledge_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.knowledge_id:
            raise ValueError("knowledge_id is required")
        if not self.title:
            raise ValueError("title is required")
        if not self.evidence:
            raise ValueError("evidence must not be empty")

        object.__setattr__(
            self, "evidence", tuple(sorted(self.evidence, key=lambda e: e.observation_id))
        )

    def with_status(self, status: KnowledgeStatus) -> "Knowledge":
        return Knowledge(
            knowledge_id=self.knowledge_id,
            title=self.title,
            status=status,
            pattern=self.pattern,
            evidence=self.evidence,
            confidence=self.confidence,
            explainability=self.explainability,
            fingerprint=self.fingerprint,
            version=self.version,
            previous_knowledge_id=self.previous_knowledge_id,
        )

    def new_version(
        self,
        new_knowledge_id: str,
        confidence: KnowledgeConfidence,
        evidence: Tuple[KnowledgeEvidence, ...],
        explainability: KnowledgeExplainability,
    ) -> "Knowledge":
        """
        Produce a new Knowledge instance representing the next version of
        this knowledge item. The fingerprint is intentionally left equal to
        the value passed by the caller (LearningService), since only the
        LearningService is permitted to compute fingerprints.
        """
        return Knowledge(
            knowledge_id=new_knowledge_id,
            title=self.title,
            status=KnowledgeStatus.ACTIVE,
            pattern=self.pattern,
            evidence=evidence,
            confidence=confidence,
            explainability=explainability,
            fingerprint=self.fingerprint,
            version=self.version.next(),
            previous_knowledge_id=self.knowledge_id,
        )

    def as_dict(self) -> dict:
        return {
            "knowledge_id": self.knowledge_id,
            "title": self.title,
            "status": self.status.value,
            "pattern": self.pattern.as_dict(),
            "evidence": [e.as_dict() for e in self.evidence],
            "confidence": self.confidence.as_dict(),
            "explainability": self.explainability.as_dict(),
            "fingerprint": self.fingerprint.as_dict(),
            "version": self.version.as_dict(),
            "previous_knowledge_id": self.previous_knowledge_id,
        }
