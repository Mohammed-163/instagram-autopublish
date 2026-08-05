"""
HypothesisEngine
================
7) Hypothesis Engine

Responsibility:
- Listen to ConfidenceUpdated event.
- Generate structured, evidence-backed hypotheses for rules that exceed the
  configurable confidence threshold.
- Persist hypotheses via HypothesisService (Service Layer).
- Emit HypothesisCreated event with full explainability data.

Design:
- Extends EngineBase — confidence threshold and success criteria from
  EngineSettingsReader (not hard-coded).
- Depends on HypothesisService — never on repositories directly.
- _build_hypothesis_statement() is isolated so the text template can be
  overridden without changing engine logic.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict

from core.events import ConfidenceUpdated, HypothesisCreated
from engines.shared.engine_base import EngineBase

logger = logging.getLogger(__name__)


class HypothesisEngine(EngineBase):
    """
    Converts ConfidenceUpdated → HypothesisCreated (when confidence ≥ threshold).
    All threshold and criteria values come from EngineSettingsReader.
    """

    ENGINE_NAME = "hypothesis"

    def __init__(
        self,
        event_bus: Any,
        hypothesis_service: Any,
        health_service: Any = None,
        settings_service: Any = None,
    ) -> None:
        super().__init__(health_service=health_service, settings_service=settings_service)
        self.event_bus = event_bus
        self.hypothesis_service = hypothesis_service

    def handle_confidence_updated(self, event: ConfidenceUpdated) -> None:
        """Handle ConfidenceUpdated: generate and persist a hypothesis if confidence qualifies."""
        try:
            rule_id = event.rule_id
            confidence = event.confidence_score
            cfg = self.settings

            logger.info(
                "[HypothesisEngine] Evaluating rule %s (confidence=%.4f) for hypothesis generation",
                rule_id,
                confidence,
            )

            # Guard: skip rules below the configurable threshold
            if confidence < cfg.hypothesis_min_confidence:
                logger.info(
                    "[HypothesisEngine] Rule %s confidence %.4f below threshold %.4f — skipping",
                    rule_id,
                    confidence,
                    cfg.hypothesis_min_confidence,
                )
                return

            hypothesis_id = uuid.uuid4()
            increase_pct = cfg.hypothesis_expected_engagement_increase_pct
            min_sample = cfg.hypothesis_min_sample_size

            expected_change = self._build_hypothesis_statement(increase_pct)
            success_criteria: Dict[str, Any] = {
                "min_engagement_increase_pct": increase_pct,
                "min_sample_size": min_sample,
            }
            failure_criteria: Dict[str, Any] = {
                "max_engagement_drop_pct": -5.0,
                "p_value_threshold": 0.05,
            }
            rationale = (
                f"Hypothesis {hypothesis_id} created based on Rule {rule_id}. "
                f"Evidence: {event.reasoning}. "
                f"Expected result: {expected_change}."
            )

            # Persist via HypothesisService
            self.hypothesis_service.create(
                rule_id=rule_id,
                statement=expected_change,
                rationale=rationale,
                success_criteria=success_criteria,
                failure_criteria=failure_criteria,
                status="proposed",
            )

            # Emit HypothesisCreated with full explainability payload
            hypo_event = HypothesisCreated(
                hypothesis_id=hypothesis_id,
                rule_id=rule_id,
                reason=(
                    f"High confidence ({confidence:.4f}) observed for rule {rule_id} "
                    f"with sample size {event.sample_size}"
                ),
                expected_change=expected_change,
                success_criteria=success_criteria,
                failure_criteria=failure_criteria,
                explainability=rationale,
            )
            self.event_bus.publish(hypo_event)

            self.heartbeat("healthy")
            logger.info("[HypothesisEngine] HypothesisCreated published: %s", hypothesis_id)

        except Exception as e:
            logger.exception("[HypothesisEngine] Error generating hypothesis: %s", e)
            self.heartbeat("error", error=str(e))

    # ------------------------------------------------------------------ helpers

    def _build_hypothesis_statement(self, increase_pct: float) -> str:
        """
        Construct the hypothesis statement from configurable parameters.
        Isolated so the template can be updated without changing engine logic.
        """
        return (
            f"Increase engagement rate by {increase_pct:.0f}% "
            "when applying question-based post headers"
        )
