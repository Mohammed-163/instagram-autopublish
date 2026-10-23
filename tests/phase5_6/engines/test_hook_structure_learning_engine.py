"""
Tests for HookStructureLearningEngine (Phase 4 Part 2).

Covers: plugin discovery/loading, engine behaviour (event flow,
explainability, persistence calls), grammar_sequence construction, and
deterministic replay.
"""
from __future__ import annotations

import uuid
from unittest.mock import Mock

import pytest

from core.events import HookAnalyzed, HookFeatureExtracted, HookFeaturesStored, HookStructureLearned
from engines.hook_feature_analyzers.base_analyzer import HookFeatureAnalyzer
from engines.hook_structure_learning_engine import HookStructureLearningEngine


# ---------------------------------------------------------------------- plugin discovery

def test_plugin_discovery_finds_multiple_analyzers():
    analyzers = HookStructureLearningEngine._discover_analyzers()
    assert len(analyzers) >= 20  # every documented feature category is covered
    for analyzer in analyzers:
        assert isinstance(analyzer, HookFeatureAnalyzer)


def test_plugin_discovery_excludes_base_class_and_helpers():
    analyzers = HookStructureLearningEngine._discover_analyzers()
    class_names = {type(a).__name__ for a in analyzers}
    assert "HookFeatureAnalyzer" not in class_names


def test_plugin_discovery_feature_names_are_unique():
    analyzers = HookStructureLearningEngine._discover_analyzers()
    names = [a.feature_name for a in analyzers]
    assert len(names) == len(set(names))


def test_plugin_discovery_is_deterministically_ordered():
    first_run = [a.feature_name for a in HookStructureLearningEngine._discover_analyzers()]
    second_run = [a.feature_name for a in HookStructureLearningEngine._discover_analyzers()]
    assert first_run == second_run
    assert first_run == sorted(first_run)


def test_plugin_loading_includes_known_features():
    analyzers = HookStructureLearningEngine._discover_analyzers()
    names = {a.feature_name for a in analyzers}
    for expected in (
        "word_count", "character_count", "has_number", "has_question",
        "has_curiosity_word", "has_warning_word", "opening_word_type",
        "punctuation_density", "emoji_count",
    ):
        assert expected in names


class _FakeAnalyzer(HookFeatureAnalyzer):
    """A minimal plugin used to prove new analyzers work without engine changes."""

    @property
    def feature_name(self) -> str:
        return "fake_feature"

    @property
    def version(self) -> str:
        return "9.9.9"

    def analyze(self, hook_text: str):
        return {"value": len(hook_text), "extraction_method": "count", "source": "hook_text"}


def test_engine_works_with_injected_custom_analyzer_without_modification():
    """A brand-new analyzer should work by simply being passed in — proving
    the engine has zero hard-coded knowledge of specific analyzers."""
    bus = Mock()
    service = Mock()
    structure = Mock()
    structure.id = uuid.uuid4()
    service.record_hook_structure.return_value = structure

    engine = HookStructureLearningEngine(
        event_bus=bus,
        hook_structure_service=service,
        health_service=Mock(),
        analyzers=[_FakeAnalyzer()],
    )
    event = HookAnalyzed(post_id=uuid.uuid4(), hook_text="hello", hook_type="curiosity", category="Science")
    engine.handle_hook_analyzed(event)

    call_kwargs = service.record_hook_structure.call_args[1]
    assert call_kwargs["features"] == {"fake_feature": 5}


# ---------------------------------------------------------------------- engine behaviour

@pytest.fixture
def mock_bus():
    return Mock()


@pytest.fixture
def mock_hook_structure_service():
    svc = Mock()
    structure = Mock()
    structure.id = uuid.uuid4()
    svc.record_hook_structure.return_value = structure
    return svc


@pytest.fixture
def mock_health_service():
    return Mock()


@pytest.fixture
def test_engine(mock_bus, mock_hook_structure_service, mock_health_service):
    return HookStructureLearningEngine(
        event_bus=mock_bus,
        hook_structure_service=mock_hook_structure_service,
        health_service=mock_health_service,
    )


def _event(hook_text="هل تعلم أن 5 حقائق ستغير رأيك؟", category="Science", hook_type="curiosity"):
    return HookAnalyzed(post_id=uuid.uuid4(), hook_text=hook_text, hook_type=hook_type, category=category)


def test_handle_hook_analyzed_persists_structure_and_feature_values(
    test_engine, mock_hook_structure_service
):
    event = _event()
    test_engine.handle_hook_analyzed(event)

    mock_hook_structure_service.record_hook_structure.assert_called_once()
    call_kwargs = mock_hook_structure_service.record_hook_structure.call_args[1]
    assert call_kwargs["post_id"] == event.post_id
    assert call_kwargs["hook_text"] == event.hook_text
    assert call_kwargs["category"] == "Science"
    assert call_kwargs["hook_type"] == "curiosity"
    assert isinstance(call_kwargs["features"], dict) and len(call_kwargs["features"]) > 0
    assert isinstance(call_kwargs["explainability"], dict)
    assert isinstance(call_kwargs["grammar_sequence"], list)
    assert call_kwargs["grammar_sequence"][0] == "opening"
    assert isinstance(call_kwargs["analyzer_versions"], dict)
    assert "structural_fingerprint" in call_kwargs
    assert "feature_fingerprint" in call_kwargs
    assert "fingerprint_hash" in call_kwargs

    mock_hook_structure_service.record_feature_values.assert_called_once()
    fv_kwargs = mock_hook_structure_service.record_feature_values.call_args[1]
    assert fv_kwargs["post_id"] == event.post_id
    assert fv_kwargs["features"] == call_kwargs["features"]


def test_handle_hook_analyzed_emits_events_in_order(test_engine, mock_bus):
    test_engine.handle_hook_analyzed(_event())

    published_types = [type(call.args[0]) for call in mock_bus.publish.call_args_list]
    assert published_types == [HookFeatureExtracted, HookFeaturesStored, HookStructureLearned]


def test_handle_hook_analyzed_reports_healthy_heartbeat(test_engine, mock_health_service):
    test_engine.handle_hook_analyzed(_event())
    mock_health_service.heartbeat.assert_called_once_with("hook_structure_learning", "healthy")


def test_handle_hook_analyzed_reports_error_heartbeat_on_failure(
    mock_bus, mock_health_service
):
    broken_service = Mock()
    broken_service.record_hook_structure.side_effect = RuntimeError("db down")
    engine = HookStructureLearningEngine(
        event_bus=mock_bus, hook_structure_service=broken_service, health_service=mock_health_service,
    )
    engine.handle_hook_analyzed(_event())
    args, kwargs = mock_health_service.heartbeat.call_args
    assert args[0] == "hook_structure_learning"
    assert args[1] == "error"
    assert "error" in kwargs


def test_single_broken_analyzer_does_not_break_the_others(mock_bus, mock_health_service):
    class BrokenAnalyzer(HookFeatureAnalyzer):
        @property
        def feature_name(self):
            return "broken"

        @property
        def version(self):
            return "1.0.0"

        def analyze(self, hook_text):
            raise ValueError("boom")

    service = Mock()
    structure = Mock()
    structure.id = uuid.uuid4()
    service.record_hook_structure.return_value = structure

    engine = HookStructureLearningEngine(
        event_bus=mock_bus,
        hook_structure_service=service,
        health_service=mock_health_service,
        analyzers=[BrokenAnalyzer(), _FakeAnalyzer()],
    )
    engine.handle_hook_analyzed(_event(hook_text="test"))

    call_kwargs = service.record_hook_structure.call_args[1]
    assert "broken" not in call_kwargs["features"]
    assert call_kwargs["features"]["fake_feature"] == 4
    mock_health_service.heartbeat.assert_called_once_with("hook_structure_learning", "healthy")


# ---------------------------------------------------------------------- explainability

def test_explainability_recorded_for_every_feature(test_engine, mock_hook_structure_service):
    test_engine.handle_hook_analyzed(_event())
    call_kwargs = mock_hook_structure_service.record_hook_structure.call_args[1]
    features = call_kwargs["features"]
    explainability = call_kwargs["explainability"]

    assert set(features.keys()) == set(explainability.keys())
    for feature_name, expl in explainability.items():
        assert "extraction_method" in expl
        assert "source" in expl
        assert "analyzer" in expl
        assert "analyzer_version" in expl
        assert expl["source"] == "hook_text"


# ---------------------------------------------------------------------- grammar sequence

def test_build_grammar_sequence_starts_with_opening():
    sequence = HookStructureLearningEngine.build_grammar_sequence({})
    assert sequence == ["opening"]


def test_build_grammar_sequence_includes_detected_components_in_fixed_order():
    features = {
        "has_question": {"present": True, "position": 0.9},
        "has_number": {"present": True, "position": 0.1},
        "has_curiosity_word": {"present": True, "position": 0.0},
    }
    sequence = HookStructureLearningEngine.build_grammar_sequence(features)
    # curiosity is documented before question, which is before number
    assert sequence == ["opening", "curiosity", "question", "number"]


def test_build_grammar_sequence_ignores_absent_components():
    features = {"has_question": {"present": False, "position": None}}
    sequence = HookStructureLearningEngine.build_grammar_sequence(features)
    assert sequence == ["opening"]


# ---------------------------------------------------------------------- fingerprint generation

def test_generate_fingerprints():
    features = {
        "has_question": {"present": True, "position": 0.9},
        "has_number": {"present": True, "position": 0.1},
        "has_curiosity_word": {"present": False, "position": 0.0},
    }
    grammar_sequence = ["opening", "question", "number"]
    
    structural_fp, feature_fp, fp_hash = HookStructureLearningEngine._generate_fingerprints(grammar_sequence, features)
    
    assert structural_fp == "opening+question+number"
    assert feature_fp == "has_number+has_question"
    
    import hashlib
    expected_combined = f"{structural_fp}|{feature_fp}"
    expected_hash = hashlib.sha256(expected_combined.encode('utf-8')).hexdigest()
    assert fp_hash == expected_hash

def test_generate_fingerprints_no_features():
    features = {}
    grammar_sequence = ["opening"]
    
    structural_fp, feature_fp, fp_hash = HookStructureLearningEngine._generate_fingerprints(grammar_sequence, features)
    
    assert structural_fp == "opening"
    assert feature_fp == "none"
    
    import hashlib
    expected_combined = f"{structural_fp}|{feature_fp}"
    expected_hash = hashlib.sha256(expected_combined.encode('utf-8')).hexdigest()
    assert fp_hash == expected_hash

# ---------------------------------------------------------------------- replay support (determinism)

def test_replay_is_deterministic_for_same_hook_text():
    engine = HookStructureLearningEngine(
        event_bus=Mock(), hook_structure_service=Mock(), health_service=Mock(),
    )
    hook_text = "5 أسرار عن جسمك لن تصدقها؟"
    features_1, explainability_1 = engine._run_analyzers(hook_text)
    features_2, explainability_2 = engine._run_analyzers(hook_text)

    assert features_1 == features_2
    assert explainability_1 == explainability_2
    assert (
        HookStructureLearningEngine.build_grammar_sequence(features_1)
        == HookStructureLearningEngine.build_grammar_sequence(features_2)
    )


def test_replay_full_event_reproduces_identical_persisted_payload(mock_bus):
    """Running the exact same HookAnalyzed event through two independent
    engine instances (simulating a replay on historical data) must yield
    identical persisted features/explainability/grammar_sequence."""
    event = _event(hook_text="تحذير: هذا الخطأ يدمر بشرتك")

    services = []
    for _ in range(2):
        service = Mock()
        structure = Mock()
        structure.id = uuid.uuid4()
        service.record_hook_structure.return_value = structure
        engine = HookStructureLearningEngine(
            event_bus=Mock(), hook_structure_service=service, health_service=Mock(),
        )
        engine.handle_hook_analyzed(event)
        services.append(service)

    kwargs_1 = services[0].record_hook_structure.call_args[1]
    kwargs_2 = services[1].record_hook_structure.call_args[1]

    assert kwargs_1["features"] == kwargs_2["features"]
    assert kwargs_1["explainability"] == kwargs_2["explainability"]
    assert kwargs_1["grammar_sequence"] == kwargs_2["grammar_sequence"]
    assert kwargs_1["analyzer_versions"] == kwargs_2["analyzer_versions"]
    assert kwargs_1["structural_fingerprint"] == kwargs_2["structural_fingerprint"]
    assert kwargs_1["feature_fingerprint"] == kwargs_2["feature_fingerprint"]
    assert kwargs_1["fingerprint_hash"] == kwargs_2["fingerprint_hash"]
