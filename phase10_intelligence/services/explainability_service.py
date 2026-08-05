"""
ExplainabilityService

All business logic for this layer lives here. This service reads its
thresholds/weights exclusively from Settings; no business constants
are hard-coded in this module.
"""
from __future__ import annotations

from typing import Any, Mapping

from ..domain.models import OpportunityRanking, StrategyEvaluation


class ExplainabilityService:
    """
    Produces per-feature/per-component explanations for scored artifacts,
    entirely derived from already-recorded, fingerprinted data -- no new
    non-deterministic computation is introduced here.
    """

    def explain_ranking(self, ranking: OpportunityRanking) -> Mapping[str, Any]:
        total = sum(ranking.components.values()) or 1.0
        contributions = {
            name: round(value / total, 10) for name, value in ranking.components.items()
        }
        return {
            "opportunity_id": ranking.opportunity_id,
            "rank_score": ranking.rank_score,
            "component_values": dict(ranking.components),
            "component_contribution_ratios": contributions,
            "fingerprint": ranking.fingerprint,
        }

    def explain_strategy_evaluation(self, evaluation: StrategyEvaluation) -> Mapping[str, Any]:
        total = sum(evaluation.metrics.values()) or 1.0
        contributions = {
            name: round(value / total, 10) for name, value in evaluation.metrics.items()
        }
        return {
            "strategy_id": evaluation.strategy_id,
            "fitness_score": evaluation.fitness_score,
            "metric_values": dict(evaluation.metrics),
            "metric_contribution_ratios": contributions,
            "fingerprint": evaluation.fingerprint,
        }
