"""
Tests for HookPatternDiscoveryEngine (Phase 4 Part 1, item 5 + item 3).
"""
import uuid
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.events import FeaturesExtracted, HookAnalyzed
from engines.hook_pattern_engine import HookPatternDiscoveryEngine


@pytest.fixture
def mock_bus():
    return Mock()


@pytest.fixture
def mock_post_service():
    return Mock()


@pytest.fixture
def mock_hook_service():
    return Mock()


@pytest.fixture
def mock_health_service():
    return Mock()


@pytest.fixture
def test_engine(mock_bus, mock_post_service, mock_hook_service, mock_health_service):
    return HookPatternDiscoveryEngine(
        event_bus=mock_bus,
        post_service=mock_post_service,
        hook_service=mock_hook_service,
        health_service=mock_health_service,
    )


def _post(final_text, category="Science"):
    return SimpleNamespace(final_text=final_text, category=category)


def test_extract_hook_text_uses_first_line_only():
    text = "هل تعلم أن الدماغ لا يشعر بالألم؟\nهذا سطر ثاني لا علاقة له بالهوك."
    assert HookPatternDiscoveryEngine.extract_hook_text(text) == "هل تعلم أن الدماغ لا يشعر بالألم؟"


def test_extract_hook_text_handles_empty_text():
    assert HookPatternDiscoveryEngine.extract_hook_text("") == ""


def test_classify_hook_type_detects_question(test_engine):
    features = test_engine.extract_hook_features("هل جربت هذا من قبل؟")
    assert features["has_question"] is True
    assert test_engine.classify_hook_type("هل جربت هذا من قبل؟", features) == "question"


def test_classify_hook_type_detects_number(test_engine):
    features = test_engine.extract_hook_features("5 حقائق ستغير رأيك")
    assert features["has_number"] is True
    assert test_engine.classify_hook_type("5 حقائق ستغير رأيك", features) == "number"


def test_classify_hook_type_detects_warning_keyword(test_engine):
    text = "تحذير: هذا الخطأ يدمر بشرتك"
    features = test_engine.extract_hook_features(text)
    assert test_engine.classify_hook_type(text, features) == "warning"


def test_classify_hook_type_default_fallback_is_curiosity(test_engine):
    text = "شيء عادي جدا بدون اي كلمات مفتاحية"
    features = test_engine.extract_hook_features(text)
    assert test_engine.classify_hook_type(text, features) in ("curiosity",)


def test_handle_features_extracted_records_pattern_and_emits_event(
    test_engine, mock_bus, mock_post_service, mock_hook_service, mock_health_service
):
    post_id = uuid.uuid4()
    mock_post_service.get_by_id.return_value = _post("هل جربت هذا الأمر من قبل؟", category="Science")

    event = FeaturesExtracted(post_id=post_id, features={})
    test_engine.handle_features_extracted(event)

    mock_hook_service.record_hook_pattern.assert_called_once()
    call_kwargs = mock_hook_service.record_hook_pattern.call_args[1]
    assert call_kwargs["post_id"] == post_id
    assert call_kwargs["category"] == "Science"
    assert call_kwargs["hook_type"] == "question"

    mock_bus.publish.assert_called_once()
    published = mock_bus.publish.call_args[0][0]
    assert isinstance(published, HookAnalyzed)
    assert published.post_id == post_id
    assert published.hook_type == "question"

    mock_health_service.heartbeat.assert_called_once_with("hook_pattern_discovery", "healthy")


def test_handle_features_extracted_skips_post_without_text(
    test_engine, mock_bus, mock_post_service, mock_hook_service
):
    post_id = uuid.uuid4()
    mock_post_service.get_by_id.return_value = _post(None)

    test_engine.handle_features_extracted(FeaturesExtracted(post_id=post_id, features={}))

    mock_hook_service.record_hook_pattern.assert_not_called()
    mock_bus.publish.assert_not_called()


def test_hook_features_include_all_required_keys(test_engine):
    features = test_engine.extract_hook_features("5 أسرار عن جسمك لن تصدقها؟")
    for key in (
        "word_count", "char_count", "has_number", "has_question", "has_comparison",
        "has_negation", "has_warning", "has_curiosity_word", "hook_length",
        "punctuation_density", "opening_type",
    ):
        assert key in features
