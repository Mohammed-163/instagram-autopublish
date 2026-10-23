"""
Tests for shared engine infrastructure:
- EngineSettingsReader: typed defaults, service delegation
- EngineBase: heartbeat delegation, settings lazy-init
"""
from unittest.mock import Mock

import pytest
from engines.shared.settings_reader import EngineSettingsReader
from engines.shared.engine_base import EngineBase


# ------------------------------------------------------------------ EngineSettingsReader

class FakeSettingsService:
    def __init__(self, data: dict):
        self._data = data

    def get(self, key: str, default=None):
        return self._data.get(key, default)


def test_settings_reader_returns_default_when_key_missing():
    reader = EngineSettingsReader(FakeSettingsService({}))
    assert reader.score_weight_engagement == pytest.approx(0.35)
    assert reader.hypothesis_min_confidence == pytest.approx(0.4)
    assert reader.planning_min_posts == 7


def test_settings_reader_returns_overridden_value():
    reader = EngineSettingsReader(FakeSettingsService({"scoring.weight.engagement": 0.50}))
    assert reader.score_weight_engagement == pytest.approx(0.50)


def test_settings_reader_list_default():
    reader = EngineSettingsReader(FakeSettingsService({}))
    slots = reader.planning_posting_slots
    assert isinstance(slots, list)
    assert len(slots) == 3


def test_settings_reader_list_override():
    reader = EngineSettingsReader(
        FakeSettingsService({"planning.posting_slots": ["10:00 UTC", "20:00 UTC"]})
    )
    assert reader.planning_posting_slots == ["10:00 UTC", "20:00 UTC"]


def test_settings_reader_all_score_weights_sum_to_one():
    reader = EngineSettingsReader(FakeSettingsService({}))
    total = (
        reader.score_weight_engagement
        + reader.score_weight_retention
        + reader.score_weight_virality
        + reader.score_weight_readability
        + reader.score_weight_visual
    )
    assert total == pytest.approx(1.0)


# ------------------------------------------------------------------ EngineBase

class ConcreteEngine(EngineBase):
    ENGINE_NAME = "test_engine"


def test_engine_base_heartbeat_delegates_to_health_service():
    health_svc = Mock()
    engine = ConcreteEngine(health_service=health_svc)
    engine.heartbeat("healthy")
    health_svc.heartbeat.assert_called_once_with("test_engine", "healthy")


def test_engine_base_heartbeat_with_error_kwargs():
    health_svc = Mock()
    engine = ConcreteEngine(health_service=health_svc)
    engine.heartbeat("error", error="something went wrong")
    health_svc.heartbeat.assert_called_once_with("test_engine", "error", error="something went wrong")


def test_engine_base_settings_uses_injected_service():
    fake_svc = FakeSettingsService({"decision.confidence_threshold": 0.75})
    engine = ConcreteEngine(settings_service=fake_svc)
    assert engine.settings.decision_confidence_threshold == pytest.approx(0.75)


def test_engine_base_settings_lazy_init():
    engine = ConcreteEngine(health_service=Mock())
    # _settings_reader should be None before first access
    assert engine._settings_reader is None
    _ = engine.settings
    assert engine._settings_reader is not None


def test_engine_base_heartbeat_survives_no_health_service(monkeypatch):
    """heartbeat should not raise if health service is unavailable."""
    engine = ConcreteEngine()
    # Patch the import path to force failure
    monkeypatch.setattr(
        "engines.shared.engine_base.EngineBase._resolve_health_service",
        lambda self: None,
    )
    # Should not raise
    engine.heartbeat("healthy")
