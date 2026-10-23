"""
LearningService.

Responsibilities (per specification):
    - validate candidates
    - generate fingerprints
    - store knowledge
    - version knowledge
    - prevent duplicates
    - publish events

Only LearningService may create fingerprints in this application's flow.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import List, Optional

from phase8_learning.domain.enums import KnowledgeStatus
from phase8_learning.domain.fingerprint import KnowledgeFingerprint
from phase8_learning.domain.knowledge import Knowledge, KnowledgeCandidate
from phase8_learning.domain.versioning import KnowledgeVersion
from phase8_learning.events.events import (
    KnowledgeCandidateCreated,
    KnowledgeStored,
    KnowledgeValidated,
    KnowledgeVersionCreated,
)
from phase8_learning.events.publisher import EventPublisher
from phase8_learning.repository.knowledge_repository import KnowledgeRepository


class CandidateValidationError(ValueError):
    """Raised when a KnowledgeCandidate fails validation."""


@dataclass(frozen=True)
class LearningServiceConfig:
    fingerprint_version: str
    engine_version: str
    schema_version: str
    min_confidence_threshold: float = 0.5


class LearningService:
    """
    Validates, fingerprints, versions, stores, and publishes knowledge
    derived from KnowledgeCandidate objects produced by the LearningEngine.
    """

    def __init__(
        self,
        repository: KnowledgeRepository,
        publisher: EventPublisher,
        config: LearningServiceConfig,
    ) -> None:
        self._repository = repository
        self._publisher = publisher
        self._config = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_candidate(self, candidate: KnowledgeCandidate) -> Optional[Knowledge]:
        """
        Full pipeline for a single candidate: validate -> fingerprint ->
        deduplicate/version -> store -> publish. Returns the persisted
        Knowledge, or None if the candidate was rejected by validation.
        """
        self._publisher.publish(
            KnowledgeCandidateCreated(
                candidate_title=candidate.title,
                source_observations=tuple(
                    e.observation_id for e in candidate.evidence
                ),
            )
        )

        try:
            self._validate(candidate)
        except CandidateValidationError:
            return None

        fingerprint = self._generate_fingerprint(candidate)

        existing = self._repository.find_latest_by_fingerprint(
            fingerprint.fingerprint_hash
        )

        if existing is not None:
            knowledge = self._version_existing(existing, candidate)
        else:
            knowledge = self._create_new(candidate, fingerprint)

        self._publisher.publish(
            KnowledgeValidated(
                knowledge_id=knowledge.knowledge_id,
                fingerprint_hash=knowledge.fingerprint.fingerprint_hash,
            )
        )
        self._publisher.publish(
            KnowledgeStored(
                knowledge_id=knowledge.knowledge_id,
                fingerprint_hash=knowledge.fingerprint.fingerprint_hash,
                knowledge_version=knowledge.version.knowledge_version,
            )
        )

        return knowledge

    def process_candidates(
        self, candidates: List[KnowledgeCandidate]
    ) -> List[Knowledge]:
        results: List[Knowledge] = []
        for candidate in candidates:
            knowledge = self.process_candidate(candidate)
            if knowledge is not None:
                results.append(knowledge)
        return results

    # ------------------------------------------------------------------
    # Internal steps
    # ------------------------------------------------------------------

    def _validate(self, candidate: KnowledgeCandidate) -> None:
        if not candidate.evidence:
            raise CandidateValidationError("candidate has no evidence")
        if candidate.confidence.score < self._config.min_confidence_threshold:
            raise CandidateValidationError("candidate confidence below threshold")

    def _generate_fingerprint(self, candidate: KnowledgeCandidate) -> KnowledgeFingerprint:
        """Only LearningService is permitted to build fingerprints."""
        return KnowledgeFingerprint.build(
            structural_payload=candidate.structural_payload,
            feature_payload=candidate.feature_payload,
        )

    def _create_new(
        self, candidate: KnowledgeCandidate, fingerprint: KnowledgeFingerprint
    ) -> Knowledge:
        knowledge_id = self._derive_knowledge_id(fingerprint.fingerprint_hash, 1)

        version = KnowledgeVersion(
            knowledge_version=1,
            fingerprint_version=self._config.fingerprint_version,
            engine_version=self._config.engine_version,
            schema_version=self._config.schema_version,
        )

        knowledge = Knowledge(
            knowledge_id=knowledge_id,
            title=candidate.title,
            status=KnowledgeStatus.ACTIVE,
            pattern=candidate.pattern,
            evidence=candidate.evidence,
            confidence=candidate.confidence,
            explainability=candidate.explainability,
            fingerprint=fingerprint,
            version=version,
            previous_knowledge_id=None,
        )
        self._repository.add(knowledge, sequence_hint=1)
        return knowledge

    def _version_existing(
        self, existing: Knowledge, candidate: KnowledgeCandidate
    ) -> Knowledge:
        """
        Prevent duplicates: if the newly derived candidate is identical
        (same fingerprint AND same evidence set) to the latest known
        version, return the existing knowledge unchanged rather than
        creating a new version.
        """
        existing_observation_ids = {e.observation_id for e in existing.evidence}
        candidate_observation_ids = {e.observation_id for e in candidate.evidence}

        if existing_observation_ids == candidate_observation_ids:
            return existing

        next_version_number = existing.version.knowledge_version + 1
        new_knowledge_id = self._derive_knowledge_id(
            existing.fingerprint.fingerprint_hash, next_version_number
        )

        new_knowledge = existing.new_version(
            new_knowledge_id=new_knowledge_id,
            confidence=candidate.confidence,
            evidence=candidate.evidence,
            explainability=candidate.explainability,
        )

        self._repository.update_status(existing.knowledge_id, KnowledgeStatus.SUPERSEDED)
        self._repository.add(new_knowledge, sequence_hint=1)

        self._publisher.publish(
            KnowledgeVersionCreated(
                knowledge_id=new_knowledge.knowledge_id,
                previous_knowledge_id=existing.knowledge_id,
                knowledge_version=new_knowledge.version.knowledge_version,
            )
        )

        return new_knowledge

    @staticmethod
    def _derive_knowledge_id(fingerprint_hash: str, knowledge_version: int) -> str:
        """
        Deterministically derive a knowledge_id from the fingerprint hash
        and version number. No UUIDs, no randomness, no timestamps.
        """
        raw = f"{fingerprint_hash}:{knowledge_version}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
