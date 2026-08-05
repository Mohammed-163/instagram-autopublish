"""
LearningEngine.

Input: ObservationRecorded events.

Responsibilities (per specification):
    - receive observations
    - group related observations
    - detect reusable patterns
    - build KnowledgeCandidate objects
    - calculate confidence
    - generate explainability
    - pass candidates to LearningService

Constraints:
    - LearningEngine must NOT access repositories.
    - LearningEngine must NOT create fingerprints (only LearningService may).
    - Everything must be deterministic: no random ordering, sorted
      collections/dicts throughout.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, DefaultDict, Iterable, List, Mapping, Optional, Tuple

from phase8_learning.domain.enums import EvidenceStrength, PatternType
from phase8_learning.domain.evidence import KnowledgeConfidence, KnowledgeEvidence, KnowledgePattern
from phase8_learning.domain.explainability import KnowledgeExplainability
from phase8_learning.domain.knowledge import KnowledgeCandidate
from phase8_learning.domain.versioning import KnowledgeVersion
from phase8_learning.events.events import ObservationRecorded


@dataclass(frozen=True)
class LearningEngineConfig:
    """Deterministic thresholds and identifiers used by the engine."""

    engine_version: str
    fingerprint_version: str
    schema_version: str
    min_sample_size: int = 2
    min_consistency_threshold: float = 0.5
    algorithm: str = "grouped-metric-consistency-v1"


class LearningEngine:
    """
    Transforms a batch of ObservationRecorded events into a set of
    KnowledgeCandidate objects.

    This class is intentionally repository-free and fingerprint-free: it
    only produces plain domain objects that LearningService will validate,
    fingerprint, and persist.
    """

    def __init__(
        self,
        config: LearningEngineConfig,
        candidate_sink: Optional[Callable[[KnowledgeCandidate], None]] = None,
    ) -> None:
        self._config = config
        self._candidate_sink = candidate_sink

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(
        self, observations: Iterable[ObservationRecorded]
    ) -> Tuple[KnowledgeCandidate, ...]:
        """
        Process a batch of observations end-to-end and return the
        KnowledgeCandidate objects produced, in deterministic order.

        If a candidate_sink was provided, each candidate is also passed to
        it (this is how candidates are handed off to LearningService,
        without the engine importing/depending on the service directly).
        """
        ordered_observations = self._sort_observations(observations)
        groups = self._group_related_observations(ordered_observations)

        candidates: List[KnowledgeCandidate] = []
        for group_key in sorted(groups.keys()):
            group = groups[group_key]
            candidate = self._build_candidate(group_key, group)
            if candidate is not None:
                candidates.append(candidate)
                if self._candidate_sink is not None:
                    self._candidate_sink(candidate)

        return tuple(candidates)

    # ------------------------------------------------------------------
    # Internal steps
    # ------------------------------------------------------------------

    @staticmethod
    def _sort_observations(
        observations: Iterable[ObservationRecorded],
    ) -> List[ObservationRecorded]:
        return sorted(observations, key=lambda o: (o.subject_id, o.metric_name, o.observation_id))

    def _group_related_observations(
        self, observations: List[ObservationRecorded]
    ) -> DefaultDict[Tuple[str, str], List[ObservationRecorded]]:
        """
        Group observations by (subject_id, metric_name). This is a simple,
        deterministic grouping strategy: observations about the same
        subject and the same metric are considered "related" for the
        purpose of pattern detection.
        """
        groups: DefaultDict[Tuple[str, str], List[ObservationRecorded]] = defaultdict(list)
        for observation in observations:
            key = (observation.subject_id, observation.metric_name)
            groups[key].append(observation)
        return groups

    def _build_candidate(
        self,
        group_key: Tuple[str, str],
        group: List[ObservationRecorded],
    ) -> Optional[KnowledgeCandidate]:
        if len(group) < self._config.min_sample_size:
            return None

        subject_id, metric_name = group_key
        sorted_group = sorted(group, key=lambda o: o.observation_id)

        values = [o.metric_value for o in sorted_group]
        mean_value = sum(values) / len(values)
        variance = sum((v - mean_value) ** 2 for v in values) / len(values)
        spread = max(values) - min(values)
        consistency = self._compute_consistency(spread, mean_value)

        if consistency < self._config.min_consistency_threshold:
            return None

        pattern = self._detect_pattern(subject_id, metric_name, sorted_group, consistency)
        evidence = self._build_evidence(sorted_group, consistency)
        confidence = self._calculate_confidence(sorted_group, consistency, variance)
        explainability = self._generate_explainability(
            subject_id, metric_name, sorted_group, confidence, evidence
        )

        structural_payload = {
            "pattern_type": pattern.pattern_type.value,
            "subject_id": subject_id,
            "metric_name": metric_name,
            "evidence_count": str(len(evidence)),
        }
        feature_payload = {
            "mean_value_bucket": self._bucket(mean_value),
            "consistency_bucket": self._bucket(consistency),
        }

        title = f"Pattern:{metric_name}:{subject_id}"

        return KnowledgeCandidate(
            title=title,
            pattern=pattern,
            evidence=tuple(evidence),
            confidence=confidence,
            explainability=explainability,
            structural_payload=structural_payload,
            feature_payload=feature_payload,
        )

    @staticmethod
    def _compute_consistency(spread: float, mean_value: float) -> float:
        if mean_value == 0:
            return 1.0 if spread == 0 else 0.0
        normalized_spread = min(abs(spread / mean_value), 1.0)
        return round(1.0 - normalized_spread, 6)

    @staticmethod
    def _bucket(value: float) -> str:
        """Deterministically bucket a float into a coarse string bucket."""
        rounded = round(value, 2)
        return f"{rounded:.2f}"

    def _detect_pattern(
        self,
        subject_id: str,
        metric_name: str,
        group: List[ObservationRecorded],
        consistency: float,
    ) -> KnowledgePattern:
        pattern_type = (
            PatternType.BEHAVIORAL if consistency >= 0.8 else PatternType.CORRELATIVE
        )
        description = (
            f"Repeated '{metric_name}' behavior detected for subject "
            f"'{subject_id}' across {len(group)} observations."
        )
        signature = {
            "metric_name": metric_name,
            "subject_id": subject_id,
            "sample_size": str(len(group)),
        }
        return KnowledgePattern(
            pattern_type=pattern_type, description=description, signature=signature
        )

    def _build_evidence(
        self, group: List[ObservationRecorded], consistency: float
    ) -> List[KnowledgeEvidence]:
        if consistency >= 0.8:
            strength = EvidenceStrength.STRONG
        elif consistency >= 0.5:
            strength = EvidenceStrength.MODERATE
        else:
            strength = EvidenceStrength.WEAK

        evidence = []
        for observation in group:
            attributes = {
                "metric_value": self._bucket(observation.metric_value),
            }
            attributes.update(observation.context)
            evidence.append(
                KnowledgeEvidence(
                    observation_id=observation.observation_id,
                    strength=strength,
                    attributes=attributes,
                )
            )
        return evidence

    def _calculate_confidence(
        self,
        group: List[ObservationRecorded],
        consistency: float,
        variance: float,
    ) -> KnowledgeConfidence:
        sample_size = len(group)
        sample_size_component = min(sample_size / 10.0, 1.0)
        variance_component = 1.0 / (1.0 + variance)

        score = round(
            (0.5 * consistency) + (0.3 * sample_size_component) + (0.2 * variance_component),
            6,
        )
        score = min(max(score, 0.0), 1.0)

        components = {
            "consistency_component": round(consistency, 6),
            "sample_size_component": round(sample_size_component, 6),
            "variance_component": round(variance_component, 6),
        }

        return KnowledgeConfidence(
            score=score,
            sample_size=sample_size,
            consistency=consistency,
            components=components,
        )

    def _generate_explainability(
        self,
        subject_id: str,
        metric_name: str,
        group: List[ObservationRecorded],
        confidence: KnowledgeConfidence,
        evidence: List[KnowledgeEvidence],
    ) -> KnowledgeExplainability:
        source_observations = tuple(o.observation_id for o in group)
        reason = (
            f"Observed consistent '{metric_name}' values for subject "
            f"'{subject_id}' across {len(group)} observations with "
            f"consistency={confidence.consistency}."
        )
        thresholds_used = {
            "min_sample_size": float(self._config.min_sample_size),
            "min_consistency_threshold": self._config.min_consistency_threshold,
        }
        versions = KnowledgeVersion(
            knowledge_version=1,
            fingerprint_version=self._config.fingerprint_version,
            engine_version=self._config.engine_version,
            schema_version=self._config.schema_version,
        )
        return KnowledgeExplainability(
            reason=reason,
            source_observations=source_observations,
            confidence=confidence,
            supporting_evidence=tuple(evidence),
            versions=versions,
            thresholds_used=thresholds_used,
            algorithm=self._config.algorithm,
        )
