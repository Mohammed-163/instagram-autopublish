"""
StrategyEvolutionService

All business logic for this layer lives here. This service reads its
thresholds/weights exclusively from Settings; no business constants
are hard-coded in this module.
"""
from __future__ import annotations

from typing import Any, List, Mapping

from ..config.settings import Settings
from ..domain.enums import StrategyStatus
from ..domain.models import Strategy
from ..events import EventPublisher, StrategyEvolved
from ..fingerprint import compute_fingerprint
from ..repositories.strategy_repository import StrategyRepository


class StrategyEvolutionService:
    """
    Deterministically evolves strategy parameter sets. Mutation is a pure,
    order-independent transformation over sorted parameter keys -- no
    randomness participates in the evolved parameter selection.
    """

    def __init__(self, repository: StrategyRepository, settings: Settings,
                 publisher: EventPublisher) -> None:
        self._repository = repository
        self._settings = settings
        self._publisher = publisher

    def seed(self, key: str, parameters: Mapping[str, Any]) -> Strategy:
        payload = {"key": key, "parameters": dict(parameters), "generation": 0, "parent_key": None}
        fp = compute_fingerprint(payload)
        strategy = Strategy(
            id=None, key=key, status=StrategyStatus.CANDIDATE, parameters=dict(parameters),
            generation=0, parent_key=None, fitness_score=0.0, fingerprint=fp,
        )
        return self._repository.add(strategy)

    def evolve(self, parent: Strategy, child_key: str) -> Strategy:
        """Deterministically mutate the parent's numeric parameters by a fixed rate."""
        rate = self._settings.strategy_mutation_rate
        mutated: dict = {}
        for name in sorted(parent.parameters.keys()):
            value = parent.parameters[name]
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                mutated[name] = round(value * (1.0 + rate), 10)
            else:
                mutated[name] = value

        payload = {
            "key": child_key, "parameters": mutated,
            "generation": parent.generation + 1, "parent_key": parent.key,
        }
        fp = compute_fingerprint(payload)

        child = Strategy(
            id=None, key=child_key, status=StrategyStatus.CANDIDATE, parameters=mutated,
            generation=parent.generation + 1, parent_key=parent.key, fitness_score=0.0,
            fingerprint=fp,
        )
        stored = self._repository.add(child)

        self._publisher.publish(StrategyEvolved(
            subject_key=stored.key, fingerprint=stored.fingerprint,
            payload={"generation": stored.generation, "parent_key": parent.key},
        ))
        return stored

    def select_survivors(self) -> List[Strategy]:
        return self._repository.list_top_by_fitness(self._settings.strategy_elite_retention)
