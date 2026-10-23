"""
PatternDiscoveryEngine
=======================
4) Pattern Discovery Engine

Responsibility:
- Listen to FeatureScoresCalculated event.
- Perform statistical analysis across post features and scores.
- Discover Candidate Patterns (purely statistical — no AI, no decisions, no rules).
- Emit PatternsDiscovered event for each discovered pattern.

Design:
- Extends EngineBase for heartbeat() and settings.
- Depends on FeatureService and ScoringService (Service Layer) — no repositories.
- All statistical thresholds come from EngineSettingsReader (configurable).
- Pattern builders are isolated helper methods for extensibility: adding a new
  pattern type requires only a new _detect_* method and a line in discover_patterns().
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List

from core.events import FeatureScoresCalculated, PatternsDiscovered
from engines.shared.engine_base import EngineBase

logger = logging.getLogger(__name__)


class PatternDiscoveryEngine(EngineBase):
    """
    Converts FeatureScoresCalculated → PatternsDiscovered (zero or more events).
    All thresholds are configurable via EngineSettingsReader.
    """

    ENGINE_NAME = "pattern_discovery"

    def __init__(
        self,
        event_bus: Any,
        feature_service: Any,
        scoring_service: Any,
        health_service: Any = None,
        settings_service: Any = None,
    ) -> None:
        super().__init__(health_service=health_service, settings_service=settings_service)
        self.event_bus = event_bus
        self.feature_service = feature_service
        self.scoring_service = scoring_service

    def handle_feature_scores_calculated(self, event: FeatureScoresCalculated) -> None:
        """Handle FeatureScoresCalculated: discover patterns and emit PatternsDiscovered per pattern."""
        try:
            post_id = event.post_id
            logger.info("[PatternDiscoveryEngine] Analyzing candidate patterns for post %s", post_id)

            patterns = self.discover_patterns(post_id, event.scores)

            for pattern in patterns:
                pattern_event = PatternsDiscovered(
                    pattern_id=pattern["pattern_id"],
                    pattern_name=pattern["pattern_name"],
                    conditions=pattern["conditions"],
                    confidence_score=pattern["confidence_score"],
                    metrics_summary=pattern["metrics_summary"],
                )
                self.event_bus.publish(pattern_event)
                logger.info("[PatternDiscoveryEngine] Published candidate pattern: %s", pattern["pattern_name"])

            self.heartbeat("healthy")

        except Exception as e:
            logger.exception("[PatternDiscoveryEngine] Error discovering patterns: %s", e)
            self.heartbeat("error", error=str(e))

    # ------------------------------------------------------------------ pattern discovery

    def discover_patterns(
        self,
        post_id: uuid.UUID,
        scores: Dict[str, float],
    ) -> List[Dict[str, Any]]:
        """
        Run all registered pattern detectors and return matching patterns.

        Each detector receives feature_map and score_map and returns either
        a pattern dict or None.  Adding a new pattern requires only a new
        _detect_* method here.
        """
        # Fetch via Service Layer
        feature_map = self.feature_service.get_feature_map(post_id)
        score_map = self.scoring_service.get_score_map(post_id)

        # Merge scores from the event (fresh) with persisted scores
        score_map.update(scores)

        detectors = [
            self._detect_question_engagement_pattern,
            self._detect_optimal_text_length_pattern,
        ]

        patterns: List[Dict[str, Any]] = []
        for detector in detectors:
            result = detector(post_id, feature_map, score_map)
            if result is not None:
                patterns.append(result)

        return patterns

    # ------------------------------------------------------------------ individual detectors

    def _detect_question_engagement_pattern(
        self,
        post_id: uuid.UUID,
        feature_map: Dict[str, float],
        score_map: Dict[str, float],
    ) -> Dict[str, Any] | None:
        """Question Prompt correlates with high engagement."""
        cfg = self.settings
        has_question = feature_map.get("has_question", 0.0)
        overall_score = score_map.get("overall_score", 0.0)
        engagement_score = score_map.get("engagement_score", 0.0)

        if has_question != 1.0 or overall_score < cfg.pattern_min_overall_score:
            return None

        boosted_conf = round(min(0.95, engagement_score * cfg.pattern_confidence_boost), 2)
        return {
            "pattern_id": uuid.uuid4(),
            "pattern_name": "Question Prompt High Engagement Pattern",
            "conditions": {
                "feature_key": "has_question",
                "operator": "==",
                "target_value": 1.0,
                "min_overall_score": cfg.pattern_min_overall_score,
            },
            "confidence_score": boosted_conf,
            "metrics_summary": {
                "observed_post_id": str(post_id),
                "overall_score": overall_score,
                "engagement_score": engagement_score,
            },
        }

    def _detect_optimal_text_length_pattern(
        self,
        post_id: uuid.UUID,
        feature_map: Dict[str, float],
        score_map: Dict[str, float],
    ) -> Dict[str, Any] | None:
        """Optimal text length correlates with high readability."""
        cfg = self.settings
        readability_score = score_map.get("readability_score", 0.0)
        text_length = feature_map.get("text_length", 0.0)
        opt_min = cfg.readability_optimal_min
        opt_max = cfg.readability_optimal_max

        if not (opt_min <= text_length <= opt_max) or readability_score < cfg.pattern_min_readability_score:
            return None

        return {
            "pattern_id": uuid.uuid4(),
            "pattern_name": "Optimal Text Length High Readability Pattern",
            "conditions": {
                "feature_key": "text_length",
                "operator": "between",
                "min_value": opt_min,
                "max_value": opt_max,
            },
            "confidence_score": round(readability_score, 2),
            "metrics_summary": {
                "observed_post_id": str(post_id),
                "text_length": text_length,
                "readability_score": readability_score,
            },
        }
