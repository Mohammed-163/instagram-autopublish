"""
Tests for DecisionEngine.
Engine now receives DecisionService instead of decision_logs_repository.
DecisionPolicyValidator reads threshold from EngineSettingsReader (not a constructor arg).
"""
import uuid
from unittest.mock import Mock

import pytest
from core.events import ExperimentCompleted, DecisionProposed, DecisionCreated
from engines.decision_engine import DecisionEngine, DecisionPolicyValidator
from engines.shared.settings_reader import EngineSettingsReader


# ------------------------------------------------------------------ helpers

def _make_settings_reader(threshold: float = 0.5) -> EngineSettingsReader:
    """Return a settings reader backed by a mock service returning fixed values."""
    svc = Mock()
    svc.get.side_effect = lambda key, default=None: {
        "decision.confidence_threshold": threshold,
        "decision.confidence_level": 0.88,
    }.get(key, default)
    return EngineSettingsReader(svc)


# ------------------------------------------------------------------ fixtures

@pytest.fixture
def mock_bus():
    return Mock()


@pytest.fixture
def mock_decision_service():
    return Mock()


@pytest.fixture
def mock_health_service():
    return Mock()


@pytest.fixture
def test_engine(mock_bus, mock_decision_service, mock_health_service):
    return DecisionEngine(
        event_bus=mock_bus,
        decision_service=mock_decision_service,
        health_service=mock_health_service,
    )


# ------------------------------------------------------------------ tests

def test_decision_engine_proposal_and_validation_chain(
    test_engine, mock_bus, mock_decision_service, mock_health_service
):
    experiment_id = uuid.uuid4()
    hypothesis_id = uuid.uuid4()

    event = ExperimentCompleted(
        experiment_id=experiment_id,
        hypothesis_id=hypothesis_id,
        variant_a_metrics={"engagement_rate": 0.08},
        variant_b_metrics={"engagement_rate": 0.12},
        winner="variant_b",
        summary="Variant B outperformed Variant A",
        explainability="Treatment variant scored higher",
    )

    test_engine.handle_experiment_completed(event)

    # 2 events: DecisionProposed + DecisionCreated
    assert mock_bus.publish.call_count == 2

    first_event = mock_bus.publish.call_args_list[0][0][0]
    second_event = mock_bus.publish.call_args_list[1][0][0]

    assert isinstance(first_event, DecisionProposed)
    assert first_event.rejected_alternatives != []
    assert first_event.evidence != {}

    assert isinstance(second_event, DecisionCreated)
    assert second_event.status == "approved"
    assert second_event.proposal_id == first_event.proposal_id

    # Verify DecisionService was called (not repository)
    mock_decision_service.log_engine_decision.assert_called_once()
    call_kwargs = mock_decision_service.log_engine_decision.call_args[1]
    assert "decision_type" in call_kwargs
    assert "confidence_level" in call_kwargs

    mock_health_service.heartbeat.assert_called_once_with("decision", "healthy")


def test_policy_validator_rejects_low_confidence():
    reader = _make_settings_reader(threshold=0.8)
    validator = DecisionPolicyValidator(settings_reader=reader)
    proposal = DecisionProposed(
        proposal_id=uuid.uuid4(),
        decision_type="test",
        reasoning="test",
        evidence={"data": "test"},
        confidence_level=0.3,  # below 0.8 threshold
    )
    result = validator.validate_proposal(proposal)
    assert result["valid"] is False
    assert "below policy threshold" in result["reason"]


def test_policy_validator_accepts_sufficient_confidence():
    reader = _make_settings_reader(threshold=0.5)
    validator = DecisionPolicyValidator(settings_reader=reader)
    proposal = DecisionProposed(
        proposal_id=uuid.uuid4(),
        decision_type="test",
        reasoning="test",
        evidence={"data": "present"},
        confidence_level=0.88,
    )
    result = validator.validate_proposal(proposal)
    assert result["valid"] is True


def test_policy_validator_rejects_empty_evidence():
    reader = _make_settings_reader(threshold=0.5)
    validator = DecisionPolicyValidator(settings_reader=reader)
    proposal = DecisionProposed(
        proposal_id=uuid.uuid4(),
        decision_type="test",
        reasoning="test",
        evidence={},  # empty
        confidence_level=0.9,
    )
    result = validator.validate_proposal(proposal)
    assert result["valid"] is False
    assert "evidence" in result["reason"]


def test_decision_engine_uses_service_not_repository(test_engine):
    assert hasattr(test_engine, "decision_service")
    assert not hasattr(test_engine, "decision_logs_repository")
    assert not hasattr(test_engine, "settings_repository")
