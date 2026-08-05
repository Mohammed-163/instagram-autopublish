"""
HypothesisLifecycleService

All business logic for this layer lives here. This service reads its
thresholds/weights exclusively from Settings; no business constants
are hard-coded in this module.
"""
from __future__ import annotations

from typing import Optional

from ..config.settings import Settings
from ..domain.enums import HypothesisStatus
from ..domain.models import Hypothesis, Opportunity
from ..events import EventPublisher, HypothesisProposed, HypothesisResolved
from ..fingerprint import compute_fingerprint
from ..repositories.hypothesis_repository import HypothesisRepository


class HypothesisLifecycleService:
    """Manages hypothesis proposal, activation, resolution, and expiry."""

    def __init__(self, repository: HypothesisRepository, settings: Settings,
                 publisher: EventPublisher) -> None:
        self._repository = repository
        self._settings = settings
        self._publisher = publisher

    def propose(self, key: str, statement: str, confidence: float,
                origin_opportunity: Optional[Opportunity] = None) -> Hypothesis:
        active_count = len(self._repository.list_by_status(HypothesisStatus.ACTIVE))
        status = (
            HypothesisStatus.PROPOSED
            if active_count < self._settings.hypothesis_max_active
            else HypothesisStatus.EXPIRED
        )

        payload = {
            "key": key, "statement": statement, "confidence": confidence,
            "origin_opportunity_key": origin_opportunity.key if origin_opportunity else None,
        }
        fp = compute_fingerprint(payload)

        hypothesis = Hypothesis(
            id=None, key=key, statement=statement,
            origin_opportunity_id=origin_opportunity.id if origin_opportunity else None,
            status=status, confidence=confidence, cycles_active=0, fingerprint=fp,
        )
        stored = self._repository.add(hypothesis)

        self._publisher.publish(HypothesisProposed(
            subject_key=stored.key, fingerprint=stored.fingerprint,
            payload={"status": stored.status.value},
        ))
        return stored

    def advance_cycle(self, hypothesis: Hypothesis) -> Hypothesis:
        cycles = hypothesis.cycles_active + 1
        if cycles >= self._settings.hypothesis_expiry_cycles:
            self._repository.update_status(hypothesis.key, HypothesisStatus.EXPIRED, cycles)
            return self._repository.get_by_key(hypothesis.key)
        self._repository.update_status(hypothesis.key, HypothesisStatus.ACTIVE, cycles)
        return self._repository.get_by_key(hypothesis.key)

    def resolve(self, hypothesis: Hypothesis, supported: bool) -> Hypothesis:
        status = HypothesisStatus.SUPPORTED if supported else HypothesisStatus.REFUTED
        self._repository.update_status(hypothesis.key, status, hypothesis.cycles_active)
        stored = self._repository.get_by_key(hypothesis.key)

        self._publisher.publish(HypothesisResolved(
            subject_key=stored.key, fingerprint=stored.fingerprint,
            payload={"status": stored.status.value},
        ))
        return stored
