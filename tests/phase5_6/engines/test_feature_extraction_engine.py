"""
Tests for FeatureExtractionEngine.
Engine now receives PostService + FeatureService instead of repositories.
"""
import uuid
from unittest.mock import Mock

import pytest
from core.events import ObservationRecorded, FeaturesExtracted
from engines.feature_extraction_engine import FeatureExtractionEngine


@pytest.fixture
def mock_bus():
    return Mock()


@pytest.fixture
def mock_post_service():
    svc = Mock()
    post_mock = Mock()
    post_mock.final_text = "Is this the future of AI?"
    svc.get_by_id.return_value = post_mock
    design_mock = Mock()
    design_mock.brightness = 0.85
    design_mock.contrast = 0.70
    svc.get_design_for_post.return_value = design_mock
    return svc


@pytest.fixture
def mock_feature_service():
    return Mock()


@pytest.fixture
def mock_health_service():
    return Mock()


@pytest.fixture
def test_engine(mock_bus, mock_post_service, mock_feature_service, mock_health_service):
    return FeatureExtractionEngine(
        event_bus=mock_bus,
        post_service=mock_post_service,
        feature_service=mock_feature_service,
        health_service=mock_health_service,
    )


def test_feature_extraction_extracts_text_and_design_features(
    test_engine, mock_bus, mock_post_service, mock_feature_service, mock_health_service
):
    post_id = uuid.uuid4()
    event = ObservationRecorded(post_id=post_id, observation_type="post_published")

    test_engine.handle_observation_recorded(event)

    # Verify PostService was used (not a repository)
    mock_post_service.get_by_id.assert_called_once_with(post_id)
    mock_post_service.get_design_for_post.assert_called_once_with(post_id)

    # Verify FeatureService.upsert_features was called with a feature dict
    mock_feature_service.upsert_features.assert_called_once()
    call_args = mock_feature_service.upsert_features.call_args
    saved_post_id = call_args[0][0]
    features_dict = call_args[0][1]
    assert saved_post_id == post_id
    
    # Check that our dynamic extractors added features (info density, view velocity)
    assert "information_density" in features_dict
    assert "view_velocity" in features_dict

    mock_health_service.heartbeat.assert_called_with("feature_extraction", "healthy")


def test_feature_extraction_handles_missing_post(
    mock_bus, mock_feature_service, mock_health_service
):
    no_post_svc = Mock()
    no_post_svc.get_by_id.return_value = None
    no_post_svc.get_design_for_post.return_value = None

    engine = FeatureExtractionEngine(
        event_bus=mock_bus,
        post_service=no_post_svc,
        feature_service=mock_feature_service,
        health_service=mock_health_service,
    )
    engine.handle_observation_recorded(ObservationRecorded(post_id=uuid.uuid4()))

    # Should still publish FeaturesExtracted (empty features)
    mock_bus.publish.assert_called_once()
    published = mock_bus.publish.call_args[0][0]
    assert isinstance(published, FeaturesExtracted)
    assert "information_density" in published.features
