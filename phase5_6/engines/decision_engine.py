"""
DecisionEngine
==============
9) Decision Engine

Responsibility:
- Combine Knowledge + Confidence + Experiment results into a Decision Proposal.
- Does NOT execute decisions directly.
- Emits DecisionProposed first, then passes it through DecisionPolicyValidator.
- On successful validation, logs the decision via DecisionService and emits DecisionCreated.

Design:
- Extends EngineBase — all thresholds (confidence_threshold, confidence_level)
  from EngineSettingsReader, zero hard-coded values.
- Depends on DecisionService — never on repositories directly.
- DecisionPolicyValidator is a separate, injectable policy object that reads
  its threshold from EngineSettingsReader (not a constructor argument).
- _build_proposal() and _build_decision() helpers keep the handler lean.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from core.events import ExperimentCompleted, DecisionProposed, DecisionCreated
from engines.shared.engine_base import EngineBase
from engines.shared.settings_reader import EngineSettingsReader

logger = logging.getLogger(__name__)


class DecisionPolicyValidator:
    """
    Policy validation layer for Decision Proposals.

    Reads min_confidence_threshold from EngineSettingsReader so operators can
    adjust the safety floor without deploying code.
    """

    def __init__(self, settings_reader: EngineSettingsReader) -> None:
        self._settings = settings_reader

    @property
    def _min_confidence(self) -> float:
        return self._settings.decision_confidence_threshold

    def validate_proposal(self, proposal: DecisionProposed) -> Dict[str, Any]:
        """Validate a decision proposal against active system policies."""
        threshold = self._min_confidence

        if proposal.confidence_level < threshold:
            return {
                "valid": False,
                "reason": (
                    f"Confidence level {proposal.confidence_level} "
                    f"below policy threshold {threshold}"
                ),
            }
        if not proposal.evidence:
            return {
                "valid": False,
                "reason": "Decision proposal lacks supporting evidence",
            }
        return {"valid": True, "reason": "Policy validation passed cleanly"}


class DecisionEngine(EngineBase):
    """
    Converts ExperimentCompleted → DecisionProposed → (policy check) → DecisionCreated.
    All numeric thresholds come from EngineSettingsReader.
    """

    ENGINE_NAME = "decision"

    def __init__(
        self,
        event_bus: Any,
        decision_service: Any,
        health_service: Any = None,
        settings_service: Any = None,
        validator: Optional[DecisionPolicyValidator] = None,
    ) -> None:
        super().__init__(health_service=health_service, settings_service=settings_service)
        self.event_bus = event_bus
        self.decision_service = decision_service
        # Validator injected for testability; defaults to settings-backed instance
        self._validator = validator

    @property
    def validator(self) -> DecisionPolicyValidator:
        if self._validator is None:
            self._validator = DecisionPolicyValidator(settings_reader=self.settings)
        return self._validator

    def handle_experiment_completed(self, event: ExperimentCompleted) -> None:
        """Process ExperimentCompleted → propose → validate → create decision."""
        try:
            experiment_id = event.experiment_id
            winner = event.winner

            logger.info(
                "[DecisionEngine] Processing completed experiment %s (Winner: %s)",
                experiment_id,
                winner,
            )

            proposal = self._build_proposal(event)

            # Step 1: Emit DecisionProposed
            self.event_bus.publish(proposal)
            logger.info("[DecisionEngine] DecisionProposed emitted: %s", proposal.proposal_id)

            # Step 2: Policy validation
            validation_result = self.validator.validate_proposal(proposal)
            if not validation_result["valid"]:
                logger.warning(
                    "[DecisionEngine] Proposal %s failed policy validation: %s",
                    proposal.proposal_id,
                    validation_result["reason"],
                )
                self.heartbeat("warning", error=validation_result["reason"])
                return

            # Step 3: Log validated decision via DecisionService
            action = f"Apply {winner} style to all future posts in topic"
            decision_id = uuid.uuid4()

            self.decision_service.log_engine_decision(
                decision_type=proposal.decision_type,
                reasoning=proposal.reasoning,
                evidence=proposal.evidence,
                confidence_level=proposal.confidence_level,
            )

            # Emit DecisionCreated
            decision_event = DecisionCreated(
                decision_id=decision_id,
                proposal_id=proposal.proposal_id,
                action=action,
                status="approved",
                explainability=(
                    f"Validated Decision {decision_id} (Proposal: {proposal.proposal_id}): "
                    f"{action}. Policy: {validation_result['reason']}"
                ),
            )
            self.event_bus.publish(decision_event)

            self.heartbeat("healthy")
            logger.info("[DecisionEngine] DecisionCreated published: %s", decision_id)

        except Exception as e:
            logger.exception("[DecisionEngine] Error processing decision: %s", e)
            self.heartbeat("error", error=str(e))

    # ------------------------------------------------------------------ builders

    def _build_proposal(self, event: ExperimentCompleted) -> DecisionProposed:
        """Construct a DecisionProposed event from an ExperimentCompleted event."""
        cfg = self.settings
        proposal_id = uuid.uuid4()
        reasoning = (
            f"Experiment {event.experiment_id} proved that treatment variant "
            f"{event.winner} delivers higher engagement."
        )
        evidence: Dict[str, Any] = {
            "experiment_id": str(event.experiment_id),
            "winner": event.winner,
            "variant_a_metrics": event.variant_a_metrics,
            "variant_b_metrics": event.variant_b_metrics,
        }
        rejected_alternatives: List[Dict[str, Any]] = [
            {
                "alternative": "maintain_status_quo_variant_a",
                "reason_rejected": "Variant A yielded lower engagement rate in controlled A/B test.",
            }
        ]
        return DecisionProposed(
            proposal_id=proposal_id,
            decision_type="adopt_winning_variant_formatting",
            reasoning=reasoning,
            evidence=evidence,
            confidence_level=cfg.decision_confidence_level,
            rejected_alternatives=rejected_alternatives,
            explainability=(
                f"Proposal {proposal_id}: Recommended adopting {event.winner} formatting. "
                f"Reason: {reasoning}. Evidence: {evidence}."
            ),
        )
