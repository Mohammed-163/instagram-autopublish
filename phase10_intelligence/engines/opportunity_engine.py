"""
OpportunityEngine

Engines ORCHESTRATE ONLY: they sequence calls across services and repositories
and never contain business rules, thresholds, or scoring formulas themselves.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..domain.models import Opportunity, OpportunityRanking, OpportunityValidation
from ..services.opportunity_discovery_service import OpportunityDiscoveryService
from ..services.opportunity_ranking_service import OpportunityRankingService
from ..services.opportunity_validation_service import OpportunityValidationService


class OpportunityEngine:
    """Orchestrates discovery -> validation -> ranking for a single opportunity."""

    def __init__(self, discovery: OpportunityDiscoveryService,
                 validation: OpportunityValidationService,
                 ranking: OpportunityRankingService) -> None:
        self._discovery = discovery
        self._validation = validation
        self._ranking = ranking

    def process(self, key: str, source: str, description: str, raw_signal: Mapping[str, Any],
                confidence: float, impact_estimate: float, novelty_score: float,
                evidence: Sequence[str]) -> tuple[Opportunity, OpportunityValidation, OpportunityRanking]:
        opportunity = self._discovery.discover(
            key, source, description, raw_signal, confidence, impact_estimate, novelty_score
        )
        validation = self._validation.validate(opportunity, evidence)
        ranking = self._ranking.rank(opportunity)
        return opportunity, validation, ranking
