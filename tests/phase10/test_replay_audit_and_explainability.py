"""Integration tests for replay determinism, audit trail, and explainability."""
import pytest

from phase10_intelligence.fingerprint import FingerprintMismatchError


def test_replay_is_deterministic_for_same_input(container):
    input_payload = {"a": 1, "b": 2}
    output_payload = {"result": 3}

    first = container.replay_audit_service.record_replay(
        subject_type="strategy", subject_key="strat-x", input_payload=input_payload,
        output_payload=output_payload, engine_name="StrategyEngine", engine_version="1.0.0",
    )
    second = container.replay_audit_service.record_replay(
        subject_type="strategy", subject_key="strat-x", input_payload=input_payload,
        output_payload=output_payload, engine_name="StrategyEngine", engine_version="1.0.0",
    )
    assert first.output_fingerprint == second.output_fingerprint


def test_replay_strict_mode_detects_nondeterminism(container):
    input_payload = {"a": 1, "b": 2}
    container.replay_audit_service.record_replay(
        subject_type="strategy", subject_key="strat-y", input_payload=input_payload,
        output_payload={"result": 3}, engine_name="StrategyEngine", engine_version="1.0.0",
    )
    with pytest.raises(FingerprintMismatchError):
        container.replay_audit_service.record_replay(
            subject_type="strategy", subject_key="strat-y", input_payload=input_payload,
            output_payload={"result": 4}, engine_name="StrategyEngine", engine_version="1.0.0",
        )


def test_explainability_ranking_contributions_sum_to_one(container):
    opportunity, _, ranking = container.opportunity_engine.process(
        key="opp-explain", source="scanner", description="desc", raw_signal={},
        confidence=0.8, impact_estimate=0.6, novelty_score=0.4, evidence=["e1", "e2"],
    )
    explanation = container.explainability_service.explain_ranking(ranking)
    total = sum(explanation["component_contribution_ratios"].values())
    assert abs(total - 1.0) < 1e-6
