"""
KnowledgeCoverageService.

This is the ONLY module in the codebase that contains business logic:
  - validation of inbound knowledge
  - coverage calculation orchestration (dimension scoring, gap detection)
  - deduplication (via fingerprint_hash)
  - version management
  - fingerprint invocation (delegates to domain/fingerprint.py)
  - repository persistence (delegates to the repository)
  - event publishing (delegates to the publisher abstraction)

Business thresholds used for gap detection are defined as explicit,
named constants on this service (not scattered, not hidden in the
domain layer, not hardcoded inside the engine).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from phase9_coverage.config.settings import Settings
from phase9_coverage.domain.dimensions import CoverageDimension, CoverageDimensionSet, DimensionName
from phase9_coverage.domain.fingerprint import compute_all_fingerprints
from phase9_coverage.domain.gaps import CoverageGap, CoverageGapSet, GapSeverity, GapType
from phase9_coverage.domain.inbound_events import KnowledgeValidated
from phase9_coverage.domain.models import CoverageEvidence, CoverageExplainability, CoverageProfile, KnowledgeCoverage, utc_now
from phase9_coverage.events.events import CoverageGapDetected, CoverageUpdated, KnowledgeCoverageCalculated
from phase9_coverage.events.publisher import EventPublisher
from phase9_coverage.repository.knowledge_coverage_repository import KnowledgeCoverageRepository

DEFAULT_COVERAGE_PROFILE = CoverageProfile(
    profile_id="default",
    profile_name="Default Coverage Profile",
    description="Baseline equal-weighted dimension evaluation.",
)


@dataclass(frozen=True)
class CoverageCalculationResult:
    """Return value of a calculation pass, before/after persistence."""

    coverage: KnowledgeCoverage
    is_new: bool
    superseded_coverage_id: Optional[str]


class KnowledgeCoverageService:
    """
    Business-rule owner for coverage evaluation. The engine calls into
    this service; this service calls into the repository and publisher.
    No repository logic lives outside the repository, and no
    fingerprinting logic lives outside domain/fingerprint.py.

    This service holds no numeric business constants of its own —
    every threshold and target value it uses for scoring and gap
    detection is read from Settings.
    """

    def __init__(
        self,
        repository: KnowledgeCoverageRepository,
        publisher: EventPublisher,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._publisher = publisher
        self._settings = settings

    # ---- validation ---------------------------------------------------

    def _validate(self, knowledge: KnowledgeValidated) -> None:
        if not knowledge.knowledge_id:
            raise ValueError("KnowledgeValidated.knowledge_id must be non-empty")
        if not knowledge.knowledge_versions:
            raise ValueError("KnowledgeValidated.knowledge_versions must be non-empty")
        if any(c < 0.0 or c > 1.0 for c in knowledge.confidence_scores):
            raise ValueError("confidence_scores must each be within [0.0, 1.0]")

    # ---- dimension scoring ---------------------------------------------

    def _score_topic_coverage(self, knowledge: KnowledgeValidated) -> CoverageDimension:
        topic_count = len(set(knowledge.topics))
        score = min(1.0, topic_count / max(1, self._settings.topic_coverage_target))
        return CoverageDimension(
            name=DimensionName.TOPIC_COVERAGE,
            score=score,
            signals={"distinct_topics": float(topic_count)},
            reason=f"{topic_count} distinct topic(s) observed",
        )

    def _score_category_coverage(self, knowledge: KnowledgeValidated) -> CoverageDimension:
        category_count = len(set(knowledge.categories))
        score = min(1.0, category_count / max(1, self._settings.category_coverage_target))
        return CoverageDimension(
            name=DimensionName.CATEGORY_COVERAGE,
            score=score,
            signals={"distinct_categories": float(category_count)},
            reason=f"{category_count} distinct category(ies) observed",
        )

    def _score_evidence_coverage(self, knowledge: KnowledgeValidated) -> CoverageDimension:
        score = min(1.0, knowledge.evidence_count / max(1, self._settings.evidence_coverage_target))
        return CoverageDimension(
            name=DimensionName.EVIDENCE_COVERAGE,
            score=score,
            signals={"evidence_count": float(knowledge.evidence_count)},
            reason=f"{knowledge.evidence_count} evidence item(s) observed",
        )

    def _score_confidence_coverage(self, knowledge: KnowledgeValidated) -> CoverageDimension:
        scores = knowledge.confidence_scores
        avg = sum(scores) / len(scores) if scores else 0.0
        return CoverageDimension(
            name=DimensionName.CONFIDENCE_COVERAGE,
            score=avg,
            signals={"average_confidence": avg, "sample_count": float(len(scores))},
            reason=f"average confidence {avg:.4f} across {len(scores)} sample(s)",
        )

    def _score_freshness_coverage(self, knowledge: KnowledgeValidated) -> CoverageDimension:
        # Deterministic, ratio-based freshness signal derived purely from
        # the count of freshness timestamps supplied relative to knowledge
        # version count; the *interpretation* of "fresh" belongs upstream.
        versions = max(1, len(knowledge.knowledge_versions))
        timestamps = len(knowledge.freshness_timestamps)
        score = min(1.0, timestamps / versions)
        return CoverageDimension(
            name=DimensionName.FRESHNESS_COVERAGE,
            score=score,
            signals={"timestamps": float(timestamps), "versions": float(versions)},
            reason=f"{timestamps} freshness timestamp(s) against {versions} version(s)",
        )

    def _score_diversity_coverage(self, knowledge: KnowledgeValidated) -> CoverageDimension:
        topics = len(set(knowledge.topics))
        categories = len(set(knowledge.categories))
        total_signals = topics + categories
        score = min(1.0, total_signals / max(1, self._settings.diversity_coverage_target))
        return CoverageDimension(
            name=DimensionName.DIVERSITY_COVERAGE,
            score=score,
            signals={"topics": float(topics), "categories": float(categories)},
            reason=f"{topics} topic(s) and {categories} categorie(s) combined for diversity",
        )

    def _score_knowledge_density(self, knowledge: KnowledgeValidated) -> CoverageDimension:
        versions = max(1, len(knowledge.knowledge_versions))
        density = knowledge.evidence_count / versions
        score = min(1.0, density / max(1.0, self._settings.knowledge_density_target))
        return CoverageDimension(
            name=DimensionName.KNOWLEDGE_DENSITY,
            score=score,
            signals={"evidence_per_version": density},
            reason=f"{density:.4f} evidence item(s) per knowledge version",
        )

    def _score_relationship_coverage(self, knowledge: KnowledgeValidated) -> CoverageDimension:
        relationship_count = len(set(knowledge.relationships))
        score = min(1.0, relationship_count / max(1, self._settings.relationship_coverage_target))
        return CoverageDimension(
            name=DimensionName.RELATIONSHIP_COVERAGE,
            score=score,
            signals={"distinct_relationships": float(relationship_count)},
            reason=f"{relationship_count} distinct relationship(s) observed",
        )

    def _score_all_dimensions(self, knowledge: KnowledgeValidated) -> CoverageDimensionSet:
        dimensions = (
            self._score_topic_coverage(knowledge),
            self._score_category_coverage(knowledge),
            self._score_evidence_coverage(knowledge),
            self._score_confidence_coverage(knowledge),
            self._score_freshness_coverage(knowledge),
            self._score_diversity_coverage(knowledge),
            self._score_knowledge_density(knowledge),
            self._score_relationship_coverage(knowledge),
        )
        return CoverageDimensionSet(dimensions=dimensions)

    # ---- gap detection --------------------------------------------------

    def _detect_gaps(
        self, knowledge: KnowledgeValidated, dimensions: CoverageDimensionSet
    ) -> CoverageGapSet:
        gaps: list[CoverageGap] = []

        if not knowledge.topics:
            gaps.append(
                CoverageGap(
                    gap_type=GapType.MISSING_TOPIC,
                    severity=GapSeverity.HIGH,
                    description="No topics were associated with this knowledge.",
                    related_dimension=DimensionName.TOPIC_COVERAGE.value,
                )
            )

        evidence_dim = dimensions.get(DimensionName.EVIDENCE_COVERAGE)
        if evidence_dim is not None and evidence_dim.score < self._settings.weak_evidence_threshold:
            gaps.append(
                CoverageGap(
                    gap_type=GapType.WEAK_EVIDENCE,
                    severity=GapSeverity.MEDIUM,
                    description="Evidence coverage is below the weak-evidence threshold.",
                    related_dimension=DimensionName.EVIDENCE_COVERAGE.value,
                    details={"score": f"{evidence_dim.score:.4f}"},
                )
            )

        confidence_dim = dimensions.get(DimensionName.CONFIDENCE_COVERAGE)
        if confidence_dim is not None and confidence_dim.score < self._settings.low_confidence_threshold:
            gaps.append(
                CoverageGap(
                    gap_type=GapType.LOW_CONFIDENCE,
                    severity=GapSeverity.MEDIUM,
                    description="Average confidence is below the low-confidence threshold.",
                    related_dimension=DimensionName.CONFIDENCE_COVERAGE.value,
                    details={"score": f"{confidence_dim.score:.4f}"},
                )
            )

        freshness_dim = dimensions.get(DimensionName.FRESHNESS_COVERAGE)
        if freshness_dim is not None and freshness_dim.score < self._settings.outdated_freshness_threshold:
            gaps.append(
                CoverageGap(
                    gap_type=GapType.OUTDATED_KNOWLEDGE,
                    severity=GapSeverity.LOW,
                    description="Freshness coverage suggests this knowledge may be outdated.",
                    related_dimension=DimensionName.FRESHNESS_COVERAGE.value,
                    details={"score": f"{freshness_dim.score:.4f}"},
                )
            )

        category_dim = dimensions.get(DimensionName.CATEGORY_COVERAGE)
        if category_dim is not None and category_dim.score < self._settings.imbalanced_category_threshold:
            gaps.append(
                CoverageGap(
                    gap_type=GapType.IMBALANCED_CATEGORY,
                    severity=GapSeverity.LOW,
                    description="Category coverage is imbalanced or too narrow.",
                    related_dimension=DimensionName.CATEGORY_COVERAGE.value,
                    details={"score": f"{category_dim.score:.4f}"},
                )
            )

        diversity_dim = dimensions.get(DimensionName.DIVERSITY_COVERAGE)
        if diversity_dim is not None and diversity_dim.score < self._settings.insufficient_diversity_threshold:
            gaps.append(
                CoverageGap(
                    gap_type=GapType.INSUFFICIENT_DIVERSITY,
                    severity=GapSeverity.MEDIUM,
                    description="Diversity coverage is below the minimum acceptable threshold.",
                    related_dimension=DimensionName.DIVERSITY_COVERAGE.value,
                    details={"score": f"{diversity_dim.score:.4f}"},
                )
            )

        density_dim = dimensions.get(DimensionName.KNOWLEDGE_DENSITY)
        if density_dim is not None and density_dim.score < self._settings.low_density_threshold:
            gaps.append(
                CoverageGap(
                    gap_type=GapType.LOW_DENSITY,
                    severity=GapSeverity.LOW,
                    description="Knowledge density is low relative to the density target.",
                    related_dimension=DimensionName.KNOWLEDGE_DENSITY.value,
                    details={"score": f"{density_dim.score:.4f}"},
                )
            )

        relationship_dim = dimensions.get(DimensionName.RELATIONSHIP_COVERAGE)
        if relationship_dim is not None and relationship_dim.score < self._settings.sparse_relationship_threshold:
            gaps.append(
                CoverageGap(
                    gap_type=GapType.SPARSE_RELATIONSHIP,
                    severity=GapSeverity.LOW,
                    description="Relationship coverage is sparse.",
                    related_dimension=DimensionName.RELATIONSHIP_COVERAGE.value,
                    details={"score": f"{relationship_dim.score:.4f}"},
                )
            )

        return CoverageGapSet(gaps=tuple(gaps))

    # ---- orchestration --------------------------------------------------

    def calculate_coverage(
        self,
        knowledge: KnowledgeValidated,
        coverage_profile: Optional[CoverageProfile] = None,
    ) -> CoverageCalculationResult:
        """
        Full orchestration: validate -> score dimensions -> detect gaps
        -> fingerprint -> deduplicate -> persist -> publish.
        """
        self._validate(knowledge)
        profile = coverage_profile or DEFAULT_COVERAGE_PROFILE

        dimensions = self._score_all_dimensions(knowledge)
        gaps = self._detect_gaps(knowledge, dimensions)

        structural_fp, feature_fp, fingerprint_hash = compute_all_fingerprints(
            knowledge_id=knowledge.knowledge_id,
            knowledge_versions=knowledge.knowledge_versions,
            coverage_profile_id=profile.profile_id,
            coverage_dimensions=dimensions,
            detected_gaps=gaps,
            fingerprint_version=self._settings.fingerprint_version,
        )

        # ---- deduplication: identical fingerprint_hash -> return existing
        existing = self._repository.get_by_fingerprint_hash(fingerprint_hash)
        if existing is not None:
            return CoverageCalculationResult(
                coverage=existing, is_new=False, superseded_coverage_id=None
            )

        coverage_score = dimensions.average_score()
        confidence_dim = dimensions.get(DimensionName.CONFIDENCE_COVERAGE)
        coverage_confidence = confidence_dim.score if confidence_dim else 0.0

        explainability = CoverageExplainability(
            coverage_method="weighted_dimension_average_v1",
            coverage_reason=(
                f"Coverage score derived from the unweighted average of "
                f"{len(dimensions.dimensions)} evaluated dimensions."
            ),
            dimensions_evaluated=tuple(
                d.name.value for d in dimensions.as_sorted_tuple()
            ),
            gaps_detected=tuple(g.gap_type.value for g in gaps.as_sorted_tuple()),
            confidence_reason=(
                "Confidence coverage dimension score is used directly as "
                "the overall coverage confidence."
            ),
            versions={
                "schema_version": self._settings.schema_version,
                "engine_version": self._settings.engine_version,
                "fingerprint_version": self._settings.fingerprint_version,
                "coverage_version": self._settings.coverage_version,
            },
        )

        coverage_id = str(uuid.uuid4())
        created_at = utc_now()

        coverage = KnowledgeCoverage(
            coverage_id=coverage_id,
            knowledge_id=knowledge.knowledge_id,
            coverage_profile=profile,
            coverage_score=coverage_score,
            coverage_dimensions=dimensions,
            detected_gaps=gaps,
            coverage_confidence=coverage_confidence,
            fingerprint=fingerprint_hash,
            structural_fingerprint=structural_fp,
            feature_fingerprint=feature_fp,
            fingerprint_hash=fingerprint_hash,
            fingerprint_version=self._settings.fingerprint_version,
            engine_version=self._settings.engine_version,
            schema_version=self._settings.schema_version,
            created_at=created_at,
            versions={
                "schema_version": self._settings.schema_version,
                "engine_version": self._settings.engine_version,
                "fingerprint_version": self._settings.fingerprint_version,
                "coverage_version": self._settings.coverage_version,
            },
            explainability=explainability,
        )

        # ---- version management: find prior coverage for this knowledge
        previous = self._repository.get_latest_for_knowledge(knowledge.knowledge_id)

        self._repository.add(coverage)
        self._repository.add_transition(
            coverage_id=coverage.coverage_id,
            previous_coverage_id=previous.coverage_id if previous else None,
            knowledge_id=knowledge.knowledge_id,
            previous_score=previous.coverage_score if previous else None,
            new_score=coverage.coverage_score,
            occurred_at=created_at,
        )
        self._repository.flush()
        self._repository.commit()

        self._publish_events(coverage=coverage, previous=previous, occurred_at=created_at)

        return CoverageCalculationResult(
            coverage=coverage,
            is_new=True,
            superseded_coverage_id=previous.coverage_id if previous else None,
        )

    def _publish_events(
        self,
        *,
        coverage: KnowledgeCoverage,
        previous: Optional[KnowledgeCoverage],
        occurred_at: datetime,
    ) -> None:
        self._publisher.publish(
            KnowledgeCoverageCalculated(coverage=coverage, occurred_at=occurred_at)
        )

        if not coverage.detected_gaps.is_empty():
            self._publisher.publish(
                CoverageGapDetected(
                    coverage_id=coverage.coverage_id,
                    knowledge_id=coverage.knowledge_id,
                    gap_count=len(coverage.detected_gaps.gaps),
                    occurred_at=occurred_at,
                )
            )

        if previous is not None:
            self._publisher.publish(
                CoverageUpdated(
                    coverage_id=coverage.coverage_id,
                    knowledge_id=coverage.knowledge_id,
                    previous_coverage_id=previous.coverage_id,
                    previous_score=previous.coverage_score,
                    new_score=coverage.coverage_score,
                    occurred_at=occurred_at,
                )
            )

    # ---- read-only query passthroughs (still no logic beyond delegation)

    def get_latest_for_knowledge(self, knowledge_id: str) -> Optional[KnowledgeCoverage]:
        return self._repository.get_latest_for_knowledge(knowledge_id)

    def get_by_id(self, coverage_id: str) -> Optional[KnowledgeCoverage]:
        return self._repository.get_by_id(coverage_id)
