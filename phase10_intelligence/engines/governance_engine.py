"""
GovernanceEngine

Engines ORCHESTRATE ONLY: they sequence calls across services and repositories
and never contain business rules, thresholds, or scoring formulas themselves.
"""
from __future__ import annotations

from ..domain.models import GovernanceReview
from ..services.governance_service import GovernanceService
from ..services.replay_audit_service import ReplayAuditService


class GovernanceEngine:
    """Orchestrates governance review and its corresponding audit trail entry."""

    def __init__(self, governance_service: GovernanceService,
                 replay_audit_service: ReplayAuditService) -> None:
        self._governance_service = governance_service
        self._replay_audit_service = replay_audit_service

    def review_and_audit(self, subject_type: str, subject_key: str, risk_score: float,
                          approvals: int, rationale: str) -> GovernanceReview:
        review = self._governance_service.review(subject_type, subject_key, risk_score, approvals, rationale)
        self._replay_audit_service.append_audit(
            event_type="governance.decided", subject_type=subject_type, subject_key=subject_key,
            payload={"decision": review.decision.value, "risk_score": risk_score},
        )
        return review
