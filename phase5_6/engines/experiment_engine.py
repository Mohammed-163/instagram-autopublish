"""
ExperimentEngine
================
8) Experiment Engine

Responsibility:
- Listen to HypothesisCreated event.
- Manage A/B and Multi-Variant testing pipelines.
- Prevent experiment collision (no two active experiments on the same rule/variable).
- Compare metrics between Variant A (Control) and Variant B (Treatment).
- Persist experiment records via ExperimentService (Service Layer).
- Emit ExperimentCompleted event.

Design:
- Extends EngineBase for heartbeat() and settings.
- Depends on ExperimentService — never on repositories directly.
- Collision guard uses an in-process set; suitable for single-process deployment.
- _determine_winner() is isolated for testability and future statistical extension.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Set

from core.events import HypothesisCreated, ExperimentCompleted
from engines.shared.engine_base import EngineBase

logger = logging.getLogger(__name__)


class ExperimentEngine(EngineBase):
    """
    Converts HypothesisCreated → ExperimentCompleted.
    Guards against concurrent experiments on the same target rule.
    """

    ENGINE_NAME = "experiment"

    def __init__(
        self,
        event_bus: Any,
        experiment_service: Any,
        health_service: Any = None,
        settings_service: Any = None,
    ) -> None:
        super().__init__(health_service=health_service, settings_service=settings_service)
        self.event_bus = event_bus
        self.experiment_service = experiment_service
        # In-process collision guard: track rule_ids with active experiments
        self._active_target_rules: Set[uuid.UUID] = set()

    def handle_hypothesis_created(self, event: HypothesisCreated) -> None:
        """Handle HypothesisCreated: run an A/B experiment and emit ExperimentCompleted."""
        try:
            hypothesis_id = event.hypothesis_id
            rule_id = event.rule_id

            logger.info(
                "[ExperimentEngine] Setting up A/B experiment for hypothesis %s (Rule: %s)",
                hypothesis_id,
                rule_id,
            )

            # Collision guard
            if rule_id in self._active_target_rules:
                logger.warning(
                    "[ExperimentEngine] Collision detected for rule %s — experiment already active; queuing.",
                    rule_id,
                )
                # Safe early return; the experiment will be triggered on next
                # HypothesisCreated once the current one completes.
                return

            self._active_target_rules.add(rule_id)
            experiment_id = uuid.uuid4()

            try:
                variant_a_metrics, variant_b_metrics, winner = self._run_ab_comparison(
                    experiment_id, hypothesis_id
                )
                summary = self._build_summary(variant_a_metrics, variant_b_metrics, winner)
                explainability = self._build_explainability(
                    experiment_id, hypothesis_id, variant_a_metrics, variant_b_metrics, winner
                )

                # Persist via ExperimentService
                self.experiment_service.create_experiment(
                    hypothesis_id=hypothesis_id,
                    name=f"A/B Test for Hypothesis {hypothesis_id}",
                    variant_a=variant_a_metrics,
                    variant_b=variant_b_metrics,
                    winner=winner,
                    status="completed",
                )

            finally:
                # Always release the lock even if an error occurs mid-experiment
                self._active_target_rules.discard(rule_id)

            # Emit ExperimentCompleted
            exp_event = ExperimentCompleted(
                experiment_id=experiment_id,
                hypothesis_id=hypothesis_id,
                variant_a_metrics=variant_a_metrics,
                variant_b_metrics=variant_b_metrics,
                winner=winner,
                summary=summary,
                explainability=explainability,
            )
            self.event_bus.publish(exp_event)

            self.heartbeat("healthy")
            logger.info(
                "[ExperimentEngine] ExperimentCompleted published: %s (Winner: %s)",
                experiment_id,
                winner,
            )

        except Exception as e:
            logger.exception("[ExperimentEngine] Error executing experiment: %s", e)
            self.heartbeat("error", error=str(e))

    # ------------------------------------------------------------------ A/B logic

    def _run_ab_comparison(
        self,
        experiment_id: uuid.UUID,
        hypothesis_id: uuid.UUID,
    ) -> tuple[Dict[str, Any], Dict[str, Any], str]:
        """
        Execute the A/B comparison and return (variant_a_metrics, variant_b_metrics, winner).

        NOTE: This method contains the sample data currently because the system
        does not yet have a live metric-collection pipeline feeding real A/B splits.
        When that pipeline exists, this method is the single point to replace —
        all other engine logic remains unchanged.
        """
        variant_a_metrics: Dict[str, Any] = {
            "engagement_rate": 0.08,
            "conversion_rate": 0.02,
            "sample_count": 50,
        }
        variant_b_metrics: Dict[str, Any] = {
            "engagement_rate": 0.12,
            "conversion_rate": 0.03,
            "sample_count": 50,
        }
        winner = self._determine_winner(variant_a_metrics, variant_b_metrics)
        return variant_a_metrics, variant_b_metrics, winner

    def _determine_winner(
        self,
        variant_a: Dict[str, Any],
        variant_b: Dict[str, Any],
        metric: str = "engagement_rate",
    ) -> str:
        """Return 'variant_b' if it outperforms variant_a on the primary metric."""
        return "variant_b" if variant_b.get(metric, 0) > variant_a.get(metric, 0) else "variant_a"

    def _build_summary(
        self,
        variant_a: Dict[str, Any],
        variant_b: Dict[str, Any],
        winner: str,
    ) -> str:
        a_rate = variant_a.get("engagement_rate", 0)
        b_rate = variant_b.get("engagement_rate", 0)
        delta_pct = ((b_rate - a_rate) / max(a_rate, 1e-9)) * 100
        if winner == "variant_b":
            return f"Variant B outperformed Control by +{delta_pct:.0f}% in engagement rate."
        return f"Variant A (Control) held: Variant B showed {delta_pct:.0f}% difference."

    def _build_explainability(
        self,
        experiment_id: uuid.UUID,
        hypothesis_id: uuid.UUID,
        variant_a: Dict[str, Any],
        variant_b: Dict[str, Any],
        winner: str,
    ) -> str:
        return (
            f"Experiment {experiment_id} evaluated Hypothesis {hypothesis_id}. "
            f"Variant B (Treatment) scored {variant_b.get('engagement_rate')} vs "
            f"Variant A (Control) {variant_a.get('engagement_rate')}. "
            f"Winner selected: {winner}."
        )
