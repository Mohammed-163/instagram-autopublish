"""
ResearchEngine

Engines ORCHESTRATE ONLY: they sequence calls across services and repositories
and never contain business rules, thresholds, or scoring formulas themselves.
"""
from __future__ import annotations

from typing import Optional

from ..domain.models import Experiment, Hypothesis, Opportunity
from ..services.experiment_lifecycle_service import ExperimentLifecycleService
from ..services.hypothesis_lifecycle_service import HypothesisLifecycleService


class ResearchEngine:
    """Orchestrates hypothesis proposal and experiment planning/analysis."""

    def __init__(self, hypothesis_service: HypothesisLifecycleService,
                 experiment_service: ExperimentLifecycleService) -> None:
        self._hypothesis_service = hypothesis_service
        self._experiment_service = experiment_service

    def propose_and_plan(self, hypothesis_key: str, statement: str, confidence: float,
                          experiment_key: str,
                          origin_opportunity: Optional[Opportunity] = None) -> tuple[Hypothesis, Optional[Experiment]]:
        hypothesis = self._hypothesis_service.propose(
            hypothesis_key, statement, confidence, origin_opportunity
        )
        experiment = self._experiment_service.plan(experiment_key, hypothesis)
        return hypothesis, experiment

    def analyze_and_resolve(self, experiment: Experiment, hypothesis: Hypothesis,
                             sample_size: int, effect_size: float, p_value: float) -> tuple[Experiment, Hypothesis]:
        analyzed = self._experiment_service.record_result(experiment, sample_size, effect_size, p_value)
        supported = self._experiment_service.is_significant(analyzed)
        resolved_hypothesis = self._hypothesis_service.resolve(hypothesis, supported)
        return analyzed, resolved_hypothesis
