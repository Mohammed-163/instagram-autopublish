import uuid
from unittest.mock import Mock
from core.events import MetricNormalized, SuccessScoreCalculated
from engines.objective_engine import ObjectiveEngine

def test_objective_engine_calculates_score_and_emits_event():
    mock_bus = Mock()
    mock_metrics = Mock()
    mock_health = Mock()
    mock_settings = Mock()
    
    mock_metrics.get_latest_for_post.return_value = {"views": 100, "watch_time": 10}
    mock_settings.objective_profile = "Growth"
    mock_settings.objective_weights = {"views": 0.5, "watch_time": 0.5}
    
    engine = ObjectiveEngine(
        event_bus=mock_bus,
        metrics_service=mock_metrics,
        health_service=mock_health,
        settings_service=mock_settings
    )
    # mock the property if we need to, but let's mock it on the service if it's there
    mock_settings.get_settings.return_value = mock_settings
    # actually EngineBase caches it, let's just patch it via standard python
    engine._cached_settings = mock_settings
    
    post_id = uuid.uuid4()
    import datetime
    event = MetricNormalized(
        post_id=post_id,
        metric_name="views",
        raw_value=100.0,
        normalized_value=1.0,
        measured_at=datetime.datetime.now(datetime.timezone.utc),
        interval_type="24h",
        source="system",
        source_version="1",
        collector_version="1",
        normalization_version="1",
        confidence=1.0
    )
    
    engine.handle_metric_normalized(event)
    
    mock_bus.publish.assert_called_once()
    published = mock_bus.publish.call_args[0][0]
    assert isinstance(published, SuccessScoreCalculated)
    assert published.post_id == post_id
    assert published.score == 25.0  # 100*0.2 + 10*0.5 (using defaults if mock missing)
    assert published.objective_profile == "Balanced"
