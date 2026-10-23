"""
Tests for PatternDiscoveryEngine.
Engine now receives FeatureService + ScoringService instead of repositories.
"""
import uuid
from unittest.mock import Mock

import pytest
from core.events import FeatureScoresCalculated, PatternsDiscovered
from engines.pattern_discovery_engine import PatternDiscoveryEngine


@pytest.fixture
def mock_bus():
    return Mock()


@pytest.fixture
def mock_feature_service():
    svc = Mock()
    svc.get_feature_map.return_value = {
        "has_question": 1.0,
        "text_length": 150.0,
    }
    return svc


@pytest.fixture
def mock_scoring_service():
    svc = Mock()
    svc.get_score_map.return_value = {}
    return svc


@pytest.fixture
def mock_health_service():
    return Mock()


@pytest.fixture
def test_engine(mock_bus, mock_feature_service, mock_scoring_service, mock_health_service):
    return PatternDiscoveryEngine(
        event_bus=mock_bus,
        feature_service=mock_feature_service,
        scoring_service=mock_scoring_service,
        health_service=mock_health_service,
    )


def test_pattern_discovery_emits_patterns_for_high_score_question_post(
    test_engine, mock_bus, mock_feature_service, mock_health_service
):
    post_id = uuid.uuid4()
    # Scores supplied via event (overall >= 0.5 threshold from settings default)
    scores = {
        "overall_score": 0.85,
        "engagement_score": 0.70,
        "readability_score": 0.9,
    }
    event = FeatureScoresCalculated(post_id=post_id, scores=scores)

    test_engine.handle_feature_scores_calculated(event)

    # Verify FeatureService and ScoringService were used
    mock_feature_service.get_feature_map.assert_called_once_with(post_id)

    # Should publish at least one PatternsDiscovered
    assert mock_bus.publish.call_count >= 1
    for call in mock_bus.publish.call_args_list:
        evt = call[0][0]
        assert isinstance(evt, PatternsDiscovered)
        assert evt.confidence_score > 0

    mock_health_service.heartbeat.assert_called_once_with("pattern_discovery", "healthy")


def test_pattern_discovery_emits_no_patterns_for_low_scores(
    mock_bus, mock_health_service
):
    feature_svc = Mock()
    feature_svc.get_feature_map.return_value = {"has_question": 0.0, "text_length": 50.0}
    scoring_svc = Mock()
    scoring_svc.get_score_map.return_value = {}

    engine = PatternDiscoveryEngine(
        event_bus=mock_bus,
        feature_service=feature_svc,
        scoring_service=scoring_svc,
        health_service=mock_health_service,
    )
    engine.handle_feature_scores_calculated(
        FeatureScoresCalculated(post_id=uuid.uuid4(), scores={"overall_score": 0.1, "engagement_score": 0.1, "readability_score": 0.1})
    )

    # No patterns should be discovered
    mock_bus.publish.assert_not_called()
    mock_health_service.heartbeat.assert_called_once_with("pattern_discovery", "healthy")


def test_pattern_discovery_uses_services_not_repositories(
    test_engine, mock_feature_service, mock_scoring_service
):
    """Confirm the engine holds service references, not repositories."""
    assert hasattr(test_engine, "feature_service")
    assert hasattr(test_engine, "scoring_service")
    assert not hasattr(test_engine, "features_repo")
    assert not hasattr(test_engine, "scores_repo")
