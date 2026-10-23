"""
HookKnowledgeEngine
====================
Phase 4 Part 1 — item 4 (Hook Knowledge Engine).

Responsibility:
- Listen to HookAnalyzed.
- Look up the post's success score (via ScoringService — Service Layer,
  never a repository) once it is available.
- Update the rolling (category, hook_type) statistic via HookService.
- When a statistic accumulates enough samples and confidence to qualify as
  a proven "Hook Rule" (category -> hook_type -> success_level), emit
  HookRuleCreated.

Example of what this produces, purely from data:
    Science -> Curiosity -> High Success
    Psychology -> Question -> Medium Success

No hard-coded rules: success_level/confidence are recomputed by HookService
from the accumulated sample every time a new observation lands.
"""
from __future__ import annotations

import logging
from typing import Any

from core.events import HookAnalyzed, HookRuleCreated
from engines.shared.engine_base import EngineBase

logger = logging.getLogger(__name__)


class HookKnowledgeEngine(EngineBase):
    """Converts HookAnalyzed -> HookRuleCreated (only once a statistic
    crosses the configured sample-size/confidence bar)."""

    ENGINE_NAME = "hook_knowledge"

    def __init__(
        self,
        event_bus: Any,
        hook_service: Any,
        scoring_service: Any,
        health_service: Any = None,
        settings_service: Any = None,
    ) -> None:
        super().__init__(health_service=health_service, settings_service=settings_service)
        self.event_bus = event_bus
        self.hook_service = hook_service
        self.scoring_service = scoring_service

    def handle_hook_analyzed(self, event: HookAnalyzed) -> None:
        try:
            category = event.category or "General"
            hook_type = event.hook_type

            score_map = self.scoring_service.get_score_map(event.post_id)
            success_score = float(score_map.get("overall_score", 0.0))

            cfg = self.settings
            statistic = self.hook_service.record_observation(
                category=category,
                hook_type=hook_type,
                success_score=success_score,
                min_sample_size=cfg.hook_min_sample_size,
                high_threshold=cfg.hook_high_success_threshold,
                medium_threshold=cfg.hook_medium_success_threshold,
                rule_confidence_threshold=cfg.hook_rule_confidence_threshold,
            )

            if statistic is not None and getattr(statistic, "is_rule", False):
                rule_event = HookRuleCreated(
                    statistic_id=statistic.id,
                    category=category,
                    hook_type=hook_type,
                    success_level=statistic.success_level,
                    confidence=float(statistic.confidence),
                    sample_size=statistic.sample_size,
                )
                self.event_bus.publish(rule_event)
                logger.info(
                    "[HookKnowledgeEngine] Hook rule: %s -> %s -> %s (confidence=%.2f, n=%d)",
                    category, hook_type, statistic.success_level, float(statistic.confidence),
                    statistic.sample_size,
                )

            self.heartbeat("healthy")

        except Exception as e:
            logger.exception("[HookKnowledgeEngine] Error updating hook knowledge: %s", e)
            self.heartbeat("error", error=str(e))
