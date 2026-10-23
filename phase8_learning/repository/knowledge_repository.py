"""
KnowledgeRepository.

Responsibilities (per specification):
    - CRUD
    - lookup by fingerprint
    - lookup by version
    - lookup active knowledge

No business logic lives here. All validation, fingerprinting, and
versioning decisions are made by LearningService before calling this
repository.
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from phase8_learning.database.models import (
    KnowledgeEvidenceModel,
    KnowledgeModel,
    KnowledgePatternModel,
    KnowledgeTransitionModel,
    KnowledgeVersionModel,
)
from phase8_learning.domain.enums import EvidenceStrength, KnowledgeStatus, PatternType
from phase8_learning.domain.evidence import KnowledgeConfidence, KnowledgeEvidence, KnowledgePattern
from phase8_learning.domain.explainability import KnowledgeExplainability
from phase8_learning.domain.fingerprint import KnowledgeFingerprint
from phase8_learning.domain.knowledge import Knowledge
from phase8_learning.domain.versioning import KnowledgeVersion


class KnowledgeRepository:
    """SQLAlchemy-backed repository for the Knowledge aggregate."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, knowledge: Knowledge, sequence_hint: int = 1) -> None:
        model = self._to_model(knowledge)
        self._session.add(model)
        self._session.flush()

        self._session.add(
            KnowledgeVersionModel(
                knowledge_id=knowledge.knowledge_id,
                knowledge_version=knowledge.version.knowledge_version,
                fingerprint_version=knowledge.version.fingerprint_version,
                engine_version=knowledge.version.engine_version,
                schema_version=knowledge.version.schema_version,
                previous_knowledge_id=knowledge.previous_knowledge_id,
            )
        )
        self._session.add(
            KnowledgeTransitionModel(
                knowledge_id=knowledge.knowledge_id,
                sequence=sequence_hint,
                from_status=None,
                to_status=knowledge.status.value,
            )
        )
        self._session.flush()

    def get(self, knowledge_id: str) -> Optional[Knowledge]:
        model = self._session.get(KnowledgeModel, knowledge_id)
        return self._to_domain(model) if model else None

    def update_status(
        self, knowledge_id: str, new_status: KnowledgeStatus
    ) -> Optional[Knowledge]:
        model = self._session.get(KnowledgeModel, knowledge_id)
        if model is None:
            return None

        previous_status = model.status
        model.status = new_status.value
        self._session.flush()

        next_sequence = (
            max((t.sequence for t in model.transitions), default=0) + 1
        )
        self._session.add(
            KnowledgeTransitionModel(
                knowledge_id=knowledge_id,
                sequence=next_sequence,
                from_status=previous_status,
                to_status=new_status.value,
            )
        )
        self._session.flush()
        return self._to_domain(model)

    def delete(self, knowledge_id: str) -> bool:
        model = self._session.get(KnowledgeModel, knowledge_id)
        if model is None:
            return False
        self._session.delete(model)
        self._session.flush()
        return True

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    def find_by_fingerprint(self, fingerprint_hash: str) -> List[Knowledge]:
        models = (
            self._session.query(KnowledgeModel)
            .filter(KnowledgeModel.fingerprint_hash == fingerprint_hash)
            .order_by(KnowledgeModel.knowledge_version.asc())
            .all()
        )
        return [self._to_domain(m) for m in models]

    def find_latest_by_fingerprint(self, fingerprint_hash: str) -> Optional[Knowledge]:
        model = (
            self._session.query(KnowledgeModel)
            .filter(KnowledgeModel.fingerprint_hash == fingerprint_hash)
            .order_by(KnowledgeModel.knowledge_version.desc())
            .first()
        )
        return self._to_domain(model) if model else None

    def find_by_version(
        self, knowledge_id_lineage: str, knowledge_version: int
    ) -> Optional[Knowledge]:
        version_row = (
            self._session.query(KnowledgeVersionModel)
            .filter(
                KnowledgeVersionModel.knowledge_id == knowledge_id_lineage,
                KnowledgeVersionModel.knowledge_version == knowledge_version,
            )
            .first()
        )
        if version_row is None:
            return None
        return self.get(version_row.knowledge_id)

    def find_active(self) -> List[Knowledge]:
        models = (
            self._session.query(KnowledgeModel)
            .filter(KnowledgeModel.status == KnowledgeStatus.ACTIVE.value)
            .order_by(KnowledgeModel.knowledge_id.asc())
            .all()
        )
        return [self._to_domain(m) for m in models]

    # ------------------------------------------------------------------
    # Mapping helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_model(knowledge: Knowledge) -> KnowledgeModel:
        pattern = knowledge.pattern
        return KnowledgeModel(
            knowledge_id=knowledge.knowledge_id,
            title=knowledge.title,
            status=knowledge.status.value,
            fingerprint_hash=knowledge.fingerprint.fingerprint_hash,
            structural_fingerprint=knowledge.fingerprint.structural_fingerprint,
            feature_fingerprint=knowledge.fingerprint.feature_fingerprint,
            knowledge_version=knowledge.version.knowledge_version,
            fingerprint_version=knowledge.version.fingerprint_version,
            engine_version=knowledge.version.engine_version,
            schema_version=knowledge.version.schema_version,
            confidence_score=knowledge.confidence.score,
            confidence_sample_size=knowledge.confidence.sample_size,
            confidence_consistency=knowledge.confidence.consistency,
            confidence_components=dict(sorted(knowledge.confidence.components.items())),
            explainability=knowledge.explainability.as_dict(),
            previous_knowledge_id=knowledge.previous_knowledge_id,
            evidence=[
                KnowledgeEvidenceModel(
                    observation_id=e.observation_id,
                    strength=e.strength.value,
                    attributes=dict(sorted(e.attributes.items())),
                )
                for e in knowledge.evidence
            ],
            patterns=[
                KnowledgePatternModel(
                    pattern_type=pattern.pattern_type.value,
                    description=pattern.description,
                    signature=dict(sorted(pattern.signature.items())),
                )
            ],
        )

    @staticmethod
    def _to_domain(model: KnowledgeModel) -> Knowledge:
        pattern_model = model.patterns[0] if model.patterns else None
        pattern = KnowledgePattern(
            pattern_type=PatternType(pattern_model.pattern_type)
            if pattern_model
            else PatternType.STRUCTURAL,
            description=pattern_model.description if pattern_model else "",
            signature=pattern_model.signature if pattern_model else {},
        )

        evidence = tuple(
            KnowledgeEvidence(
                observation_id=e.observation_id,
                strength=EvidenceStrength(e.strength),
                attributes=e.attributes or {},
            )
            for e in sorted(model.evidence, key=lambda e: e.observation_id)
        )

        confidence = KnowledgeConfidence(
            score=model.confidence_score,
            sample_size=model.confidence_sample_size,
            consistency=model.confidence_consistency,
            components=model.confidence_components or {},
        )

        version = KnowledgeVersion(
            knowledge_version=model.knowledge_version,
            fingerprint_version=model.fingerprint_version,
            engine_version=model.engine_version,
            schema_version=model.schema_version,
        )

        fingerprint = KnowledgeFingerprint(
            structural_fingerprint=model.structural_fingerprint,
            feature_fingerprint=model.feature_fingerprint,
            fingerprint_hash=model.fingerprint_hash,
        )

        explainability_data = model.explainability
        explainability = KnowledgeExplainability(
            reason=explainability_data["reason"],
            source_observations=tuple(explainability_data["source_observations"]),
            confidence=confidence,
            supporting_evidence=evidence,
            versions=version,
            thresholds_used=explainability_data["thresholds_used"],
            algorithm=explainability_data["algorithm"],
        )

        return Knowledge(
            knowledge_id=model.knowledge_id,
            title=model.title,
            status=KnowledgeStatus(model.status),
            pattern=pattern,
            evidence=evidence,
            confidence=confidence,
            explainability=explainability,
            fingerprint=fingerprint,
            version=version,
            previous_knowledge_id=model.previous_knowledge_id,
        )
