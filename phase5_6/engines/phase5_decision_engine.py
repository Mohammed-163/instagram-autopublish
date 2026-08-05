"""
Phase5DecisionEngine
=====================
Phase 5 (Part 1) — Decision Layer Foundation.

Responsibility:
- Subscribe ONLY to WeeklyStrategyCompleted.
- Consume the completed strategy (via StrategyService — never a repository).
- Evaluate strategy candidates and build DecisionCandidate objects.
- Call Phase5DecisionService to fingerprint, score, and persist them.

This engine must NEVER:
- access repositories directly
- publish content
- schedule execution
- execute decisions

All configurable parameters (which scoring profile to use) come from
SettingsService — never hardcoded.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from core.events import WeeklyStrategyCompleted
from engines.decision.decision_candidate import DecisionCandidate, DecisionEvidence, DecisionExplainability
from engines.shared.engine_base import EngineBase

logger = logging.getLogger(__name__)


class Phase5DecisionEngine(EngineBase):
    """Converts WeeklyStrategyCompleted -> DecisionCandidate(s) -> Phase5DecisionService."""

    ENGINE_NAME = "phase5_decision"

    def __init__(
        self,
        event_bus: Any,
        phase5_decision_service: Any,
        strategy_service: Any,
        health_service: Any = None,
        settings_service: Any = None,
    ) -> None:
        super().__init__(health_service=health_service, settings_service=settings_service)
        self.event_bus = event_bus
        self.phase5_decision_service = phase5_decision_service
        self.strategy_service = strategy_service

    def handle_weekly_strategy_completed(self, event: WeeklyStrategyCompleted) -> None:
        """Handle WeeklyStrategyCompleted: evaluate candidates, propose decisions."""
        try:
            logger.info(
                "[Phase5DecisionEngine] Evaluating strategy version %s for decisions",
                event.strategy_version_id,
            )

            settings = self._load_settings()
            objective_profile = settings.get("objective_profile", "Balanced")
            scoring_profile = settings.get("scoring_profile", objective_profile)

            strategy_candidates = self.strategy_service.get_candidates_for_version(event.strategy_version_id)

            proposed = 0
            for strategy_candidate in strategy_candidates:
                try:
                    decision_candidate = self._build_candidate(
                        event=event,
                        strategy_candidate=strategy_candidate,
                        objective_profile=objective_profile,
                    )
                    self.phase5_decision_service.persist_candidate(
                        decision_candidate, scoring_profile=scoring_profile
                    )
                    proposed += 1
                except Exception as e:
                    logger.warning(
                        "[Phase5DecisionEngine] Failed to build/persist decision candidate for "
                        "strategy candidate %s: %s",
                        getattr(strategy_candidate, "id", "?"),
                        e,
                    )

            self.heartbeat("healthy")
            logger.info(
                "[Phase5DecisionEngine] Proposed %d decision candidate(s) for strategy version %s",
                proposed,
                event.strategy_version_id,
            )

        except Exception as e:
            logger.exception("[Phase5DecisionEngine] Error evaluating strategy candidates: %s", e)
            self.heartbeat("error", error=str(e))

    # ------------------------------------------------------------------ helpers

    def _load_settings(self) -> Dict[str, Any]:
        """Load decision-detection settings from SettingsService."""
        try:
            return self._settings_service.get("decision_detection", {}) or {}
        except Exception:
            return {}

    def _build_candidate(
        self,
        event: WeeklyStrategyCompleted,
        strategy_candidate: Any,
        objective_profile: str,
    ) -> DecisionCandidate:
        """Build an (unscored) DecisionCandidate from a StrategyCandidate.
        Scoring/fingerprinting happens downstream in Phase5DecisionService."""
        based_on = getattr(strategy_candidate, "based_on", None) or {}
        related_opportunities: List[str] = []
        if isinstance(based_on, dict) and based_on.get("source") == "opportunity" and based_on.get("opportunity_id"):
            related_opportunities.append(str(based_on["opportunity_id"]))

        evidence = DecisionEvidence(
            strategy_version_id=str(event.strategy_version_id),
            strategy_candidate_id=str(getattr(strategy_candidate, "id", "")),
            category=getattr(strategy_candidate, "category", ""),
            topic=getattr(strategy_candidate, "topic", ""),
            hook_type=getattr(strategy_candidate, "hook_type", ""),
            is_experiment=bool(getattr(strategy_candidate, "is_experiment", False)),
            source_confidence=float(getattr(strategy_candidate, "confidence", 0.0) or 0.0),
            source_expected_success=float(getattr(strategy_candidate, "expected_success", 0.0) or 0.0),
            raw=based_on,
        )

        explainability = DecisionExplainability(
            reasons=(
                f"Derived from strategy candidate {evidence.strategy_candidate_id} "
                f"({evidence.category} / {evidence.hook_type}).",
                getattr(strategy_candidate, "reason", "") or "",
            ),
            method="strategy_candidate_evaluation",
            evidence=evidence,
            thresholds_used={"objective_profile": objective_profile},
            confidence=evidence.source_confidence,
        )

        return DecisionCandidate(
            decision_type="execute_strategy_candidate",
            objective_profile=objective_profile,
            explainability=explainability,
            related_opportunities=tuple(related_opportunities),
            confidence=evidence.source_confidence,
            expected_gain=evidence.source_expected_success,
            risk=None,
            versions={
                "strategy_version_id": str(event.strategy_version_id),
                "strategy_version_number": str(event.version_number),
            },
        )
