"""
OpportunityValidationService

All business logic for this layer lives here. This service reads its
thresholds/weights exclusively from Settings; no business constants
are hard-coded in this module.
"""
from __future__ import annotations

from typing import Sequence

from ..config.settings import Settings
from ..domain.models import Opportunity, OpportunityValidation
from ..events import EventPublisher, OpportunityValidated
from ..fingerprint import compute_fingerprint
from ..repositories.opportunity_repository import OpportunityRepository


class OpportunityValidationService:
    """Validates a discovered opportunity against evidence-count thresholds."""

    def __init__(self, repository: OpportunityRepository, settings: Settings,
                 publisher: EventPublisher) -> None:
        self._repository = repository
        self._settings = settings
        self._publisher = publisher

    def validate(self, opportunity: Opportunity, evidence: Sequence[str]) -> OpportunityValidation:
        is_valid = len(evidence) >= self._settings.opportunity_validation_min_evidence_count
        reasons = list(evidence) if is_valid else [
            f"insufficient_evidence:{len(evidence)}<{self._settings.opportunity_validation_min_evidence_count}"
        ]

        payload = {
            "opportunity_key": opportunity.key,
            "opportunity_fingerprint": opportunity.fingerprint,
            "is_valid": is_valid,
            "evidence_count": len(evidence),
            "reasons": sorted(reasons),
        }
        fp = compute_fingerprint(payload)

        validation = OpportunityValidation(
            id=None, opportunity_id=opportunity.id, is_valid=is_valid,
            evidence_count=len(evidence), reasons=sorted(reasons), fingerprint=fp,
        )
        stored = self._repository.add_validation(validation)

        self._publisher.publish(OpportunityValidated(
            subject_key=opportunity.key, fingerprint=stored.fingerprint,
            payload={"is_valid": is_valid},
        ))
        return stored
