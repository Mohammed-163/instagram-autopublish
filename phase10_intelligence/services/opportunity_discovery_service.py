"""
OpportunityDiscoveryService

All business logic for this layer lives here. This service reads its
thresholds/weights exclusively from Settings; no business constants
are hard-coded in this module.
"""
from __future__ import annotations

from typing import Any, Mapping

from ..config.settings import Settings
from ..domain.enums import OpportunityStatus
from ..domain.models import Opportunity
from ..events import EventPublisher, OpportunityDiscovered
from ..fingerprint import compute_fingerprint
from ..repositories.opportunity_repository import OpportunityRepository


class OpportunityDiscoveryService:
    """Turns raw, deterministic signals into candidate Opportunity records."""

    def __init__(self, repository: OpportunityRepository, settings: Settings,
                 publisher: EventPublisher) -> None:
        self._repository = repository
        self._settings = settings
        self._publisher = publisher

    def discover(self, key: str, source: str, description: str,
                 raw_signal: Mapping[str, Any], confidence: float,
                 impact_estimate: float, novelty_score: float) -> Opportunity:
        existing = self._repository.get_by_key(key)
        if existing is not None:
            return existing

        payload = {
            "key": key, "source": source, "description": description,
            "raw_signal": dict(raw_signal), "confidence": confidence,
            "impact_estimate": impact_estimate, "novelty_score": novelty_score,
        }
        fp = compute_fingerprint(payload)

        status = (
            OpportunityStatus.DISCOVERED
            if confidence >= self._settings.opportunity_min_score
            else OpportunityStatus.REJECTED
        )

        opportunity = Opportunity(
            id=None, key=key, source=source, description=description,
            raw_signal=dict(raw_signal), status=status, confidence=confidence,
            impact_estimate=impact_estimate, novelty_score=novelty_score, fingerprint=fp,
        )
        stored = self._repository.add(opportunity)

        self._publisher.publish(OpportunityDiscovered(
            subject_key=stored.key, fingerprint=stored.fingerprint,
            payload={"status": stored.status.value},
        ))
        return stored
