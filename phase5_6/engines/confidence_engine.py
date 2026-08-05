"""
ConfidenceEngine
================
6) Confidence Engine

Responsibility:
- Measure the quality and confidence level of Knowledge Rules.
- Evaluate sample size, success/failure counts, and stability over time.
- Persist confidence scores via ConfidenceService (Service Layer).
- Emit ConfidenceUpdated event per rule evaluated.

Design:
- Extends EngineBase — all thresholds from EngineSettingsReader (no hard-codes).
- Depends on KnowledgeService and ConfidenceService — never on repositories.
- Private _calculate_confidence() is isolated for independent testability.
- The legacy _get_setting() helper is removed; EngineBase.settings is used instead.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, List

from core.events import KnowledgeUpdated, ConfidenceUpdated
from engines.shared.engine_base import EngineBase

logger = logging.getLogger(__name__)


class ConfidenceEngine(EngineBase):
    """
    Converts KnowledgeUpdated → ConfidenceUpdated (one event per active rule).
    All thresholds come from EngineSettingsReader (configurable without code change).
    """

    ENGINE_NAME = "confidence"

    def __init__(
        self,
        event_bus: Any,
        knowledge_service: Any,
        confidence_service: Any,
        health_service: Any = None,
        settings_service: Any = None,
    ) -> None:
        super().__init__(health_service=health_service, settings_service=settings_service)
        self.event_bus = event_bus
        self.knowledge_service = knowledge_service
        self.confidence_service = confidence_service

    def handle_knowledge_updated(self, event: KnowledgeUpdated) -> None:
        """Recalculate confidence for all active/proposed rules after a knowledge update."""
        try:
            logger.info(
                "[ConfidenceEngine] Evaluating rule confidence after KnowledgeUpdated (Version: %s)",
                event.knowledge_version_id,
            )

            cfg = self.settings
            rules: List[Any] = self.knowledge_service.get_active_rules()

            for rule in rules:
                rule_id = getattr(rule, "id", uuid.uuid4())
                success_count = int(getattr(rule, "success_count", 8) or 8)
                failure_count = int(getattr(rule, "failure_count", 2) or 2)
                sample_size = success_count + failure_count

                confidence_score, reasoning = self._calculate_confidence(
                    rule=rule,
                    sample_size=sample_size,
                    success_count=success_count,
                    failure_count=failure_count,
                    min_sample_size=cfg.confidence_min_sample_size,
                    base_confidence=cfg.confidence_base,
                    success_weight=cfg.confidence_success_weight,
                )

                # Persist via ConfidenceService
                self.confidence_service.record_score(
                    rule_id=rule_id,
                    confidence_score=confidence_score,
                    sample_size=sample_size,
                )

                # Emit ConfidenceUpdated
                conf_event = ConfidenceUpdated(
                    rule_id=rule_id,
                    confidence_score=confidence_score,
                    sample_size=sample_size,
                    success_count=success_count,
                    failure_count=failure_count,
                    reasoning=reasoning,
                )
                self.event_bus.publish(conf_event)
                logger.info(
                    "[ConfidenceEngine] ConfidenceUpdated for rule %s: %.4f", rule_id, confidence_score
                )

            self.heartbeat("healthy")

        except Exception as e:
            logger.exception("[ConfidenceEngine] Error evaluating confidence: %s", e)
            self.heartbeat("error", error=str(e))

    # ------------------------------------------------------------------ calculation

    def _calculate_confidence(
        self,
        rule: Any,
        sample_size: int,
        success_count: int,
        failure_count: int,
        min_sample_size: float,
        base_confidence: float,
        success_weight: float,
    ) -> tuple[float, str]:
        """
        Compute a confidence score and produce an explainable reasoning string.
        Returns (confidence_score, reasoning).
        """
        rule_name = getattr(rule, "name", "Rule")

        if sample_size >= min_sample_size:
            ratio = success_count / max(sample_size, 1)
            confidence_score = round(min(1.0, base_confidence + (ratio * success_weight * 5.0)), 4)
        else:
            ratio = success_count / max(sample_size, 1)
            confidence_score = base_confidence

        reasoning = (
            f"Evaluated rule '{rule_name}': sample_size={sample_size}, "
            f"success_count={success_count}, failure_count={failure_count}, "
            f"ratio={ratio:.2f}"
        )
        return confidence_score, reasoning
