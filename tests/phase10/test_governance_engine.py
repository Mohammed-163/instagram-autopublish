"""Integration test for governance review + audit trail."""
from phase10_intelligence.domain.enums import GovernanceDecision


def test_governance_approves_low_risk_with_approval(container):
    review = container.governance_engine.review_and_audit(
        subject_type="strategy", subject_key="strat-1",
        risk_score=0.2, approvals=1, rationale="low risk, reviewed",
    )
    assert review.decision == GovernanceDecision.APPROVED


def test_governance_rejects_high_risk(container):
    review = container.governance_engine.review_and_audit(
        subject_type="strategy", subject_key="strat-2",
        risk_score=0.95, approvals=5, rationale="too risky",
    )
    assert review.decision == GovernanceDecision.REJECTED
