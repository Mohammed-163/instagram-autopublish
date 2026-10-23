"""
StrategyEngine

Engines ORCHESTRATE ONLY: they sequence calls across services and repositories
and never contain business rules, thresholds, or scoring formulas themselves.
"""
from __future__ import annotations

from typing import Any, List, Mapping

from ..domain.models import Strategy, StrategyEvaluation
from ..services.strategy_evolution_service import StrategyEvolutionService
from ..services.strategy_optimization_service import StrategyOptimizationService


class StrategyEngine:
    """Orchestrates strategy seeding, evolution, and fitness-based optimization."""

    def __init__(self, evolution_service: StrategyEvolutionService,
                 optimization_service: StrategyOptimizationService) -> None:
        self._evolution_service = evolution_service
        self._optimization_service = optimization_service

    def seed(self, key: str, parameters: Mapping[str, Any]) -> Strategy:
        return self._evolution_service.seed(key, parameters)

    def evolve_generation(self, parents: List[Strategy]) -> List[Strategy]:
        children: List[Strategy] = []
        for parent in parents:
            child_key = f"{parent.key}::gen{parent.generation + 1}"
            children.append(self._evolution_service.evolve(parent, child_key))
        return children

    def evaluate(self, strategy: Strategy, metrics: Mapping[str, float]) -> StrategyEvaluation:
        return self._optimization_service.evaluate(strategy, metrics)

    def prune(self) -> int:
        return self._optimization_service.retire_underperformers()

    def survivors(self) -> List[Strategy]:
        return self._evolution_service.select_survivors()
