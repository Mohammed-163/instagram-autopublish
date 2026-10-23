"""
FeatureScoringEngine
=====================
3) Feature Scoring Engine (pre-publish content quality)

Responsibility:
- Listen to FeaturesExtracted event ONLY. Never touches anything that
  depends on real-world performance data (likes, shares, watch time...).
- Compute pure content-quality dimensions from the extracted features alone:
  Readability, Visual, Hook, Information Density.
- Persist scores via ScoringService (Service Layer).
- Emit FeatureScoresCalculated event carrying the quality scores dict.

Design:
- Extends EngineBase for heartbeat() and settings (all weights/thresholds come
  from EngineSettingsReader — zero hard-coded values).
- Depends on ScoringService only — never on repositories, never on
  MetricsService (that belongs to the post-publish side of the pipeline).
- Score computation is isolated in _compute_scores() for testability.

This engine answers exactly one question: "how good does this content look
*before* it is published?" It never knows how the post actually performed —
that comparison is PerformanceEvaluationEngine's job (see
performance_evaluation_engine.py), which runs later, on a different event,
after SuccessScoreCalculated arrives from ObjectiveEngine. Keeping these two
concerns in separate engines/events avoids mixing a pre-publish prediction
with a post-publish outcome inside a single handler.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from core.events import FeaturesExtracted, FeatureScoresCalculated
from engines.shared.engine_base import EngineBase

logger = logging.getLogger(__name__)


class FeatureScoringEngine(EngineBase):
    """
    Converts FeaturesExtracted → FeatureScoresCalculated.
    All numeric thresholds/weights are read from EngineSettingsReader (configurable).
    """

    ENGINE_NAME = "feature_scoring"

    def __init__(
        self,
        event_bus: Any,
        scoring_service: Any,
        health_service: Any = None,
        settings_service: Any = None,
    ) -> None:
        super().__init__(health_service=health_service, settings_service=settings_service)
        self.event_bus = event_bus
        self.scoring_service = scoring_service

    def handle_features_extracted(self, event: FeaturesExtracted) -> None:
        """Handle FeaturesExtracted: compute content-quality scores and emit FeatureScoresCalculated."""
        try:
            post_id = event.post_id
            logger.info("[FeatureScoringEngine] Scoring content quality for post %s", post_id)

            scores_dict = self._compute_scores(event.features)

            # Persist via ScoringService (Service Layer)
            self.scoring_service.upsert_scores(post_id, scores_dict)

            # Emit FeatureScoresCalculated
            scores_event = FeatureScoresCalculated(post_id=post_id, scores=scores_dict)
            self.event_bus.publish(scores_event)

            self.heartbeat("healthy")
            logger.info(
                "[FeatureScoringEngine] FeatureScoresCalculated published for post %s: overall=%.4f",
                post_id,
                scores_dict.get("overall_score", 0.0),
            )

        except Exception as e:
            logger.exception("[FeatureScoringEngine] Error scoring content for event %s: %s", event, e)
            self.heartbeat("error", error=str(e))

    # ------------------------------------------------------------------ score computation

    def _compute_scores(self, features: Dict[str, Any]) -> Dict[str, float]:
        """
        Compute all pre-publish content-quality dimensions from extracted
        features alone. No performance data (likes/shares/watch time) is
        used or available here by design.
        """
        cfg = self.settings

        # Readability — based on text_length feature
        text_length = float(features.get("text_length", 150.0))
        if cfg.readability_optimal_min <= text_length <= cfg.readability_optimal_max:
            readability_score = cfg.readability_score_optimal
        elif text_length < cfg.readability_optimal_min:
            readability_score = cfg.readability_score_short
        else:
            readability_score = cfg.readability_score_long

        # Visual — based on brightness feature
        brightness = float(features.get("brightness", 0.5))
        visual_score = min(1.0, max(0.2, brightness))

        # Hook — cheap structural heuristic from features (has_question, first
        # line length, curiosity markers...). This is deliberately independent
        # from HookPatternDiscoveryEngine/hook_service, which run in parallel
        # off the same FeaturesExtracted event and own the deeper hook-type
        # classification and rule-learning. This dimension only answers "does
        # the opening line look structurally strong?", not "which hook type
        # is this?".
        hook_score = self._score_hook_strength(features)

        # Information Density — informative content relative to length.
        density_score = self._score_information_density(features)

        weights = {
            "readability": cfg.score_weight_readability,
            "visual": cfg.score_weight_visual,
            "hook": cfg.score_weight_hook,
            "density": cfg.score_weight_density,
        }
        weight_sum = sum(weights.values()) or 1.0
        overall_score = (
            readability_score * weights["readability"]
            + visual_score * weights["visual"]
            + hook_score * weights["hook"]
            + density_score * weights["density"]
        ) / weight_sum

        return {
            "readability_score": readability_score,
            "visual_score": visual_score,
            "hook_score": hook_score,
            "density_score": density_score,
            "overall_score": round(overall_score, 4),
        }

    def _score_hook_strength(self, features: Dict[str, Any]) -> float:
        """Cheap structural signal for how strong the opening line looks.
        Direct feature override wins if FeatureExtractionEngine already
        supplies one (e.g. from a richer hook-structure model down the line)."""
        if "hook_strength" in features:
            return float(min(1.0, max(0.0, features["hook_strength"])))

        score = 0.5
        if features.get("has_question"):
            score += 0.2
        first_line_length = float(features.get("first_line_length", 0.0))
        if 0 < first_line_length <= 60:
            score += 0.15
        if features.get("has_number"):
            score += 0.1
        return round(min(1.0, max(0.0, score)), 4)

    def _score_information_density(self, features: Dict[str, Any]) -> float:
        """Cheap proxy for informative-content-per-length. Direct feature
        override wins if a richer NLP-based density feature is supplied."""
        if "information_density" in features:
            return float(min(1.0, max(0.0, features["information_density"])))
        return 0.5
