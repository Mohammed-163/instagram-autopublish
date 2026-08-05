"""
OpportunityRankingService

All business logic for this layer lives here. This service reads its
thresholds/weights exclusively from Settings; no business constants
are hard-coded in this module.
"""
from __future__ import annotations

from ..config.settings import Settings
from ..domain.models import Opportunity, OpportunityRanking
from ..events import EventPublisher, OpportunityRanked
from ..fingerprint import compute_fingerprint
from ..repositories.opportunity_repository import OpportunityRepository


class OpportunityRankingService:
    """Computes a deterministic composite rank score for an opportunity."""

    def __init__(self, repository: OpportunityRepository, settings: Settings,
                 publisher: EventPublisher) -> None:
        self._repository = repository
        self._settings = settings
        self._publisher = publisher

    def rank(self, opportunity: Opportunity) -> OpportunityRanking:
        s = self._settings
        components = {
            "confidence": opportunity.confidence * s.opportunity_ranking_weight_confidence,
            "impact": opportunity.impact_estimate * s.opportunity_ranking_weight_impact,
            "novelty": opportunity.novelty_score * s.opportunity_ranking_weight_novelty,
        }
        rank_score = round(sum(components.values()), 10)

        payload = {
            "opportunity_key": opportunity.key,
            "opportunity_fingerprint": opportunity.fingerprint,
            "components": {k: round(v, 10) for k, v in components.items()},
            "rank_score": rank_score,
        }
        fp = compute_fingerprint(payload)

        ranking = OpportunityRanking(
            id=None, opportunity_id=opportunity.id, rank_score=rank_score,
            components=components, fingerprint=fp,
        )
        stored = self._repository.add_ranking(ranking)

        self._publisher.publish(OpportunityRanked(
            subject_key=opportunity.key, fingerprint=stored.fingerprint,
            payload={"rank_score": rank_score},
        ))
        return stored
