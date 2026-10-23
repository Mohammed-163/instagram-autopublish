"""
PerformanceEvaluationEngine
============================
Post-publish performance evaluation.

Responsibility:
- Listen to SuccessScoreCalculated event (emitted by ObjectiveEngine, based
  on real-world metrics — likes, shares, watch time...).
- Compare it against the pre-publish quality prediction already computed by
  FeatureScoringEngine (fetched via ScoringService, not recomputed).
- Compute a performance_gap: how far the actual outcome was from what the
  content quality alone predicted. A large positive gap means the post
  performed better than its content quality alone would suggest (context,
  timing, or luck mattered a lot); a large negative gap means quality looked
  good on paper but did not translate into real performance.
- Persist via ScoringService and emit PerformanceEvaluated.

Design:
- Extends EngineBase for heartbeat() and settings.
- Depends on ScoringService only — never on repositories.
- Deliberately separate from FeatureScoringEngine: this handler only ever
  runs *after* a post has real performance data, days after publish, while
  FeatureScoringEngine only ever runs *before* publish. Merging them back
  into one engine would mix two different points in the content's lifecycle
  behind a single responsibility, which is exactly what this split exists
  to avoid.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from core.events import SuccessScoreCalculated, PerformanceEvaluated
from engines.shared.engine_base import EngineBase

logger = logging.getLogger(__name__)


class PerformanceEvaluationEngine(EngineBase):
    """
    Converts SuccessScoreCalculated → PerformanceEvaluated.
    """

    ENGINE_NAME = "performance_evaluation"

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

    def handle_success_score_calculated(self, event: SuccessScoreCalculated) -> None:
        """Handle SuccessScoreCalculated: compare against predicted quality and emit PerformanceEvaluated."""
        try:
            post_id = event.post_id
            logger.info(
                "[PerformanceEvaluationEngine] Evaluating performance for post %s", post_id
            )

            # Fetch the quality prediction FeatureScoringEngine already
            # persisted pre-publish — never recomputed here.
            quality_map = self.scoring_service.get_score_map(post_id)
            predicted_quality_score = float(quality_map.get("overall_score", 0.0))

            performance_gap = round(event.score - predicted_quality_score, 4)

            explainability = self._build_explainability(
                event, predicted_quality_score, performance_gap
            )

            self.scoring_service.upsert_scores(
                post_id,
                {
                    "performance_score": event.score,
                    "performance_gap": performance_gap,
                },
            )

            evaluated_event = PerformanceEvaluated(
                post_id=post_id,
                success_score=event.score,
                predicted_quality_score=predicted_quality_score,
                performance_gap=performance_gap,
                explainability=explainability,
            )
            self.event_bus.publish(evaluated_event)

            self.heartbeat("healthy")
            logger.info(
                "[PerformanceEvaluationEngine] PerformanceEvaluated published for post %s: gap=%.4f",
                post_id,
                performance_gap,
            )

        except Exception as e:
            logger.exception(
                "[PerformanceEvaluationEngine] Error evaluating performance for event %s: %s", event, e
            )
            self.heartbeat("error", error=str(e))

    # ------------------------------------------------------------------ explainability

    def _build_explainability(
        self,
        event: SuccessScoreCalculated,
        predicted_quality_score: float,
        performance_gap: float,
    ) -> Dict[str, Any]:
        if performance_gap > 0.1:
            verdict = "outperformed_quality_prediction"
        elif performance_gap < -0.1:
            verdict = "underperformed_quality_prediction"
        else:
            verdict = "matched_quality_prediction"

        return {
            "verdict": verdict,
            "success_score": event.score,
            "predicted_quality_score": predicted_quality_score,
            "performance_gap": performance_gap,
            "objective_profile": event.objective_profile,
            "objective_version": event.objective_version,
        }
