"""Integration test for hypothesis + experiment lifecycle orchestration."""
from phase10_intelligence.domain.enums import HypothesisStatus


def test_propose_plan_analyze_resolve(container):
    hypothesis, experiment = container.research_engine.propose_and_plan(
        hypothesis_key="hyp-1", statement="Hooks with X increase retention",
        confidence=0.7, experiment_key="exp-1",
    )
    assert hypothesis.status == HypothesisStatus.PROPOSED
    assert experiment is not None

    analyzed, resolved = container.research_engine.analyze_and_resolve(
        experiment, hypothesis, sample_size=25, effect_size=0.3, p_value=0.01,
    )
    assert resolved.status == HypothesisStatus.SUPPORTED
