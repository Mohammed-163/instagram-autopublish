"""
AdaptivePlanningService

All business logic for this layer lives here. This service reads its
thresholds/weights exclusively from Settings; no business constants
are hard-coded in this module.
"""
from __future__ import annotations

from typing import List

from ..config.settings import Settings
from ..domain.models import PlanningCycle, Strategy
from ..events import EventPublisher, PlanningCycleCompleted
from ..fingerprint import compute_fingerprint
from ..repositories.planning_repository import PlanningRepository


class AdaptivePlanningService:
    """Selects strategies for the next planning cycle within a risk budget."""

    def __init__(self, repository: PlanningRepository, settings: Settings,
                 publisher: EventPublisher) -> None:
        self._repository = repository
        self._settings = settings
        self._publisher = publisher

    def plan_cycle(self, candidate_strategies: List[Strategy]) -> PlanningCycle:
        latest = self._repository.latest()
        cycle_index = (latest.cycle_index + 1) if latest else 0

        ordered = sorted(candidate_strategies, key=lambda s: (-s.fitness_score, s.key))
        selected: List[str] = []
        risk_budget_used = 0.0
        risk_per_strategy = 1.0 / max(len(ordered), 1)

        for strategy in ordered:
            if risk_budget_used + risk_per_strategy > self._settings.planning_risk_tolerance:
                break
            if len(selected) >= self._settings.planning_horizon_cycles:
                break
            selected.append(strategy.key)
            risk_budget_used = round(risk_budget_used + risk_per_strategy, 10)

        payload = {
            "cycle_index": cycle_index, "horizon": self._settings.planning_horizon_cycles,
            "selected_strategy_keys": sorted(selected), "risk_budget_used": risk_budget_used,
        }
        fp = compute_fingerprint(payload)

        cycle = PlanningCycle(
            id=None, cycle_index=cycle_index, horizon=self._settings.planning_horizon_cycles,
            selected_strategy_keys=selected, risk_budget_used=risk_budget_used, fingerprint=fp,
        )
        stored = self._repository.add(cycle)

        self._publisher.publish(PlanningCycleCompleted(
            subject_key=f"cycle:{cycle_index}", fingerprint=stored.fingerprint,
            payload={"selected_count": len(selected)},
        ))
        return stored
