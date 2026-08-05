"""
Tests for PerformanceEvaluationEngine.
Post-publish evaluation — compares SuccessScoreCalculated (real outcome)
against the quality prediction FeatureScoringEngine already persisted.
"""
import uuid
from unittest.mock import Mock

import pytest
from core.events import SuccessScoreCalculated, PerformanceEvaluated
from engines.performance_evaluation_engine import PerformanceEvaluationEngine


@pytest.fixture
def mock_bus():
    return Mock()


@pytest.fixture
def mock_scoring_service():
    svc = Mock()
    svc.get_score_map.return_value = {"overall_score": 0.6}
    return svc


@pytest.fixture
def mock_health_service():
    return Mock()


@pytest.fixture
def test_engine(mock_bus, mock_scoring_service, mock_health_service):
    return PerformanceEvaluationEngine(
        event_bus=mock_bus,
        scoring_service=mock_scoring_service,
        health_service=mock_health_service,
    )


def _make_event(post_id, score):
    return SuccessScoreCalculated(
        post_id=post_id,
        score=score,
        explainability={"details": []},
        objective_version="1.0",
        objective_profile="Balanced",
        weight_config_version="1.0",
        settings_version="1.0",
    )


def test_performance_evaluation_computes_gap_against_stored_quality_prediction(
    test_engine, mock_bus, mock_scoring_service, mock_health_service
):
    post_id = uuid.uuid4()
    event = _make_event(post_id, score=0.8)

    test_engine.handle_success_score_calculated(event)

    # Never recomputes quality — always reads what FeatureScoringEngine stored
    mock_scoring_service.get_score_map.assert_called_once_with(post_id)

    mock_scoring_service.upsert_scores.assert_called_once_with(
        post_id, {"performance_score": 0.8, "performance_gap": 0.2}
    )

    mock_bus.publish.assert_called_once()
    published = mock_bus.publish.call_args[0][0]
    assert isinstance(published, PerformanceEvaluated)
    assert published.post_id == post_id
    assert published.success_score == 0.8
    assert published.predicted_quality_score == 0.6
    assert published.performance_gap == 0.2

    mock_health_service.heartbeat.assert_called_once_with("performance_evaluation", "healthy")


def test_performance_evaluation_verdict_outperformed(test_engine):
    post_id = uuid.uuid4()
    test_engine.handle_success_score_calculated(_make_event(post_id, score=0.9))
    published = test_engine.event_bus.publish.call_args[0][0]
    assert published.explainability["verdict"] == "outperformed_quality_prediction"


def test_performance_evaluation_verdict_underperformed(mock_bus, mock_health_service):
    scoring_service = Mock()
    scoring_service.get_score_map.return_value = {"overall_score": 0.9}
    engine = PerformanceEvaluationEngine(
        event_bus=mock_bus, scoring_service=scoring_service, health_service=mock_health_service
    )
    engine.handle_success_score_calculated(_make_event(uuid.uuid4(), score=0.5))
    published = mock_bus.publish.call_args[0][0]
    assert published.explainability["verdict"] == "underperformed_quality_prediction"
