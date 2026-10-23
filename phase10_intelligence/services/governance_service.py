"""
GovernanceService

All business logic for this layer lives here. This service reads its
thresholds/weights exclusively from Settings; no business constants
are hard-coded in this module.
"""
from __future__ import annotations

from ..config.settings import Settings
from ..domain.enums import GovernanceDecision
from ..domain.models import GovernanceReview
from ..events import EventPublisher, GovernanceDecided
from ..fingerprint import compute_fingerprint
from ..repositories.governance_repository import GovernanceRepository


class GovernanceService:
    """Applies risk-based governance and policy-validation gating."""

    def __init__(self, repository: GovernanceRepository, settings: Settings,
                 publisher: EventPublisher) -> None:
        self._repository = repository
        self._settings = settings
        self._publisher = publisher

    def review(self, subject_type: str, subject_key: str, risk_score: float,
               approvals: int, rationale: str) -> GovernanceReview:
        if risk_score > self._settings.governance_max_risk_score:
            decision = GovernanceDecision.REJECTED
        elif approvals < self._settings.governance_required_approvals:
            decision = GovernanceDecision.PENDING
        else:
            decision = GovernanceDecision.APPROVED

        payload = {
            "subject_type": subject_type, "subject_key": subject_key,
            "risk_score": risk_score, "approvals": approvals, "rationale": rationale,
            "decision": decision.value,
        }
        fp = compute_fingerprint(payload)

        review = GovernanceReview(
            id=None, subject_type=subject_type, subject_key=subject_key,
            decision=decision, risk_score=risk_score, approvals=approvals,
            rationale=rationale, fingerprint=fp,
        )
        stored = self._repository.add(review)

        self._publisher.publish(GovernanceDecided(
            subject_key=subject_key, fingerprint=stored.fingerprint,
            payload={"decision": decision.value},
        ))
        return stored

    def validate_policy(self, policy_version: str) -> bool:
        """Policy validation: the active policy must match the configured version."""
        return policy_version == self._settings.policy_version
