"""
Tests for ObservationEngine.
Engine now receives AuditService instead of events_repository directly.
"""
import uuid
from unittest.mock import Mock, MagicMock

import pytest
from core.events import PostPublished, ObservationRecorded
from engines.observation_engine import ObservationEngine


@pytest.fixture
def mock_bus():
    return Mock()


@pytest.fixture
def mock_audit_service():
    return Mock()


@pytest.fixture
def mock_health_service():
    return Mock()


@pytest.fixture
def test_engine(mock_bus, mock_audit_service, mock_health_service):
    return ObservationEngine(
        event_bus=mock_bus,
        audit_service=mock_audit_service,
        health_service=mock_health_service,
    )


def test_observation_engine_records_and_publishes(test_engine, mock_bus, mock_audit_service, mock_health_service):
    post_id = uuid.uuid4()
    event = PostPublished(post_id=post_id)

    test_engine.handle_post_published(event)

    # Verify audit_service.record_event was called
    mock_audit_service.record_event.assert_called_once()
    call_kwargs = mock_audit_service.record_event.call_args[1]
    assert call_kwargs["event_type"] == "post_published"

    # Verify ObservationRecorded was published on the bus
    mock_bus.publish.assert_called_once()
    published = mock_bus.publish.call_args[0][0]
    assert isinstance(published, ObservationRecorded)
    assert published.post_id == post_id

    # Verify heartbeat reported healthy
    mock_health_service.heartbeat.assert_called_once_with("observation", "healthy")


def test_observation_engine_reports_error_on_exception(mock_bus, mock_health_service):
    broken_audit = Mock()
    broken_audit.record_event.side_effect = RuntimeError("DB down")

    engine = ObservationEngine(
        event_bus=mock_bus,
        audit_service=broken_audit,
        health_service=mock_health_service,
    )
    engine.handle_post_published(PostPublished(post_id=uuid.uuid4()))

    mock_health_service.heartbeat.assert_called_once()
    args = mock_health_service.heartbeat.call_args[0]
    assert args[1] == "error"
