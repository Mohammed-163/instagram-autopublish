"""Integration test for the Opportunity discovery/validation/ranking pipeline."""
from phase10_intelligence.domain.enums import OpportunityStatus


def test_opportunity_pipeline_end_to_end(container):
    opportunity, validation, ranking = container.opportunity_engine.process(
        key="opp-1", source="signal-scanner", description="Test opportunity",
        raw_signal={"metric": 1.0}, confidence=0.8, impact_estimate=0.6,
        novelty_score=0.5, evidence=["evidence-a", "evidence-b"],
    )
    assert opportunity.status == OpportunityStatus.DISCOVERED
    assert validation.is_valid is True
    assert ranking.rank_score > 0


def test_opportunity_rejected_below_min_score(container):
    opportunity, _, _ = container.opportunity_engine.process(
        key="opp-2", source="signal-scanner", description="Low confidence",
        raw_signal={}, confidence=0.1, impact_estimate=0.1, novelty_score=0.1,
        evidence=[],
    )
    assert opportunity.status == OpportunityStatus.REJECTED
