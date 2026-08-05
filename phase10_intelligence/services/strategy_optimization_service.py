"""
StrategyOptimizationService

All business logic for this layer lives here. This service reads its
thresholds/weights exclusively from Settings; no business constants
are hard-coded in this module.
"""
from __future__ import annotations

from typing import Mapping

from ..config.settings import Settings
from ..domain.enums import StrategyStatus
from ..domain.models import Strategy, StrategyEvaluation
from ..events import EventPublisher, StrategyOptimized
from ..fingerprint import compute_fingerprint
from ..repositories.strategy_repository import StrategyRepository


class StrategyOptimizationService:
    """Evaluates a strategy's fitness and promotes/retires it based on thresholds."""

    def __init__(self, repository: StrategyRepository, settings: Settings,
                 publisher: EventPublisher) -> None:
        self._repository = repository
        self._settings = settings
        self._publisher = publisher

    def evaluate(self, strategy: Strategy, metrics: Mapping[str, float]) -> StrategyEvaluation:
        fitness_score = round(sum(metrics.values()) / len(metrics), 10) if metrics else 0.0

        payload = {
            "strategy_key": strategy.key,
            "strategy_fingerprint": strategy.fingerprint,
            "metrics": {k: round(v, 10) for k, v in metrics.items()},
            "fitness_score": fitness_score,
        }
        fp = compute_fingerprint(payload)

        evaluation = StrategyEvaluation(
            id=None, strategy_id=strategy.id, fitness_score=fitness_score,
            metrics=metrics, fingerprint=fp,
        )
        stored_eval = self._repository.add_evaluation(evaluation)

        improvement = fitness_score - strategy.fitness_score
        new_status = (
            StrategyStatus.ACTIVE
            if improvement >= self._settings.strategy_optimization_min_improvement
            else strategy.status
        )
        self._repository.update_status_and_fitness(strategy.key, new_status, fitness_score)

        self._publisher.publish(StrategyOptimized(
            subject_key=strategy.key, fingerprint=stored_eval.fingerprint,
            payload={"fitness_score": fitness_score, "status": new_status.value},
        ))
        return stored_eval

    def retire_underperformers(self) -> int:
        active = self._repository.list_by_status(StrategyStatus.ACTIVE)
        retired = 0
        for strategy in active:
            if strategy.fitness_score < self._settings.strategy_optimization_min_improvement:
                self._repository.update_status_and_fitness(
                    strategy.key, StrategyStatus.RETIRED, strategy.fitness_score
                )
                retired += 1
        return retired
