"""Integration tests for planning and the learning feedback loop."""
def test_planning_cycle_respects_risk_tolerance(container):
    strat_a = container.strategy_engine.seed("plan-strat-a", {"w": 1.0})
    strat_b = container.strategy_engine.seed("plan-strat-b", {"w": 2.0})
    container.strategy_optimization_service.evaluate(strat_a, {"accuracy": 0.9})
    container.strategy_optimization_service.evaluate(strat_b, {"accuracy": 0.5})

    strategies = [
        container.strategy_repository.get_by_key("plan-strat-a"),
        container.strategy_repository.get_by_key("plan-strat-b"),
    ]
    cycle = container.planning_engine.plan_next_cycle(strategies, subject_type="strategy")
    assert cycle.cycle_index == 0
    assert cycle.risk_budget_used <= container.settings.planning_risk_tolerance + 1e-9


def test_learning_engine_closes_feedback_loop(container):
    feedback, calibration, review = container.learning_engine.close_loop(
        subject_type="strategy", subject_key="plan-strat-a",
        raw_confidence=0.7, outcome_score=0.9, sample_size=15,
    )
    assert feedback.outcome_score == 0.9
    assert 0.0 <= calibration.calibrated_confidence <= 1.0
    assert "sample_size" in review
