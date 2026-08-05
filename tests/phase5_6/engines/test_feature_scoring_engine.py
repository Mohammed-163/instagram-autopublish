"""
Tests for FeatureScoringEngine.
Pre-publish content-quality scoring — depends only on ScoringService,
never on MetricsService (no performance data involved).
"""
import uuid
from unittest.mock import Mock

import pytest
from core.events import FeaturesExtracted, FeatureScoresCalculated
from engines.feature_scoring_engine import FeatureScoringEngine


@pytest.fixture
def mock_bus():
    return Mock()


@pytest.fixture
def mock_scoring_service():
    return Mock()


@pytest.fixture
def mock_health_service():
    return Mock()


@pytest.fixture
def test_engine(mock_bus, mock_scoring_service, mock_health_service):
    return FeatureScoringEngine(
        event_bus=mock_bus,
        scoring_service=mock_scoring_service,
        health_service=mock_health_service,
    )


def test_feature_scoring_engine_calculates_all_quality_dimensions(
    test_engine, mock_bus, mock_scoring_service, mock_health_service
):
    post_id = uuid.uuid4()
    event = FeaturesExtracted(
        post_id=post_id,
        features={"text_length": 200.0, "brightness": 0.7, "has_question": True},
    )

    test_engine.handle_features_extracted(event)

    mock_scoring_service.upsert_scores.assert_called_once()
    call_args = mock_scoring_service.upsert_scores.call_args
    assert call_args[0][0] == post_id
    scores_dict = call_args[0][1]
    assert set(scores_dict.keys()) == {
        "readability_score",
        "visual_score",
        "hook_score",
        "density_score",
        "overall_score",
    }

    mock_bus.publish.assert_called_once()
    published = mock_bus.publish.call_args[0][0]
    assert isinstance(published, FeatureScoresCalculated)
    assert published.post_id == post_id
    assert 0.0 <= published.scores["overall_score"] <= 1.0

    mock_health_service.heartbeat.assert_called_once_with("feature_scoring", "healthy")


def test_feature_scoring_engine_never_touches_metrics_service(test_engine):
    """This engine must not know about performance data at all — the
    constructor doesn't even accept a metrics_service."""
    assert not hasattr(test_engine, "metrics_service")


def test_feature_scoring_readability_optimal_range(test_engine):
    scores = test_engine._compute_scores({"text_length": 200.0})
    assert scores["readability_score"] == test_engine.settings.readability_score_optimal


def test_feature_scoring_readability_short_text(test_engine):
    scores = test_engine._compute_scores({"text_length": 50.0})
    assert scores["readability_score"] == test_engine.settings.readability_score_short


def test_feature_scoring_readability_long_text(test_engine):
    scores = test_engine._compute_scores({"text_length": 500.0})
    assert scores["readability_score"] == test_engine.settings.readability_score_long


def test_feature_scoring_hook_strength_override(test_engine):
    """A direct hook_strength feature (e.g. from a richer hook model) wins
    over the cheap heuristic."""
    scores = test_engine._compute_scores({"hook_strength": 0.95})
    assert scores["hook_score"] == 0.95


def test_feature_scoring_hook_strength_heuristic(test_engine):
    base = test_engine._compute_scores({})["hook_score"]
    boosted = test_engine._compute_scores(
        {"has_question": True, "has_number": True, "first_line_length": 40}
    )["hook_score"]
    assert boosted > base
