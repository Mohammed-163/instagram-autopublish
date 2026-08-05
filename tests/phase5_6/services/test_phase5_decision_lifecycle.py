"""
tests/services/test_phase5_decision_lifecycle.py
================================================
Minimal Phase 5 Part 2 tests covering:
  1. Lifecycle transition validation (full 7-state graph)
  2. schedule / execute / cancel / expire lifecycle methods
  3. Transition history persistence on every call
  4. Illegal transition rejection (no side-effects)
  5. Explainability field presence on stored candidates
  6. Fingerprint determinism (order-independent, same input -> same hash)
  7. score_batch replay determinism (same order every run)

Container bootstrap is intentionally avoided — see tests/services/conftest.py.
All heavy dependencies are replaced by unittest.mock.Mock objects.
"""
from __future__ import annotations

import uuid
from unittest.mock import Mock, call

import pytest

# Direct submodule imports — avoid database.services.__init__ (see conftest.py)
from database.services.decision_scoring_service import (
    ALLOWED_TRANSITIONS,
    DecisionScoringService,
)
from database.services.phase5_decision_service import Phase5DecisionService
from core.events import (
    DecisionCancelled,
    DecisionCandidateApproved,
    DecisionCandidateRejected,
    DecisionExecuted,
    DecisionExpired,
    DecisionScheduled,
)
from engines.decision.decision_candidate import (
    DecisionCandidate,
    DecisionEvidence,
    DecisionExplainability,
)


# ================================================================== helpers

_SETTINGS_DATA = {
    "Balanced": {
        "confidence_weight": 0.45,
        "gain_weight": 0.35,
        "risk_penalty_weight": 0.20,
    },
    "Growth": {
        "confidence_weight": 0.30,
        "gain_weight": 0.55,
        "risk_penalty_weight": 0.15,
    },
}


def _settings_svc(profile_key: str = "Balanced") -> Mock:
    svc = Mock()
    svc.get.side_effect = lambda key, default=None: {
        "decision_scoring": {"profiles": _SETTINGS_DATA},
    }.get(key, default)
    return svc


def _scoring_svc() -> DecisionScoringService:
    return DecisionScoringService(settings_service=_settings_svc())


def _evidence(**kw) -> DecisionEvidence:
    defaults = dict(
        strategy_version_id=str(uuid.uuid4()),
        strategy_candidate_id=str(uuid.uuid4()),
        category="engagement",
        hook_type="question",
        source_confidence=0.70,
        source_expected_success=0.60,
    )
    defaults.update(kw)
    return DecisionEvidence(**defaults)


def _candidate(**kw) -> DecisionCandidate:
    ev = _evidence()
    exp = DecisionExplainability(
        reasons=("Derived from strategy candidate.",),
        method="strategy_candidate_evaluation",
        evidence=ev,
        confidence=ev.source_confidence,
    )
    defaults = dict(
        decision_type="execute_strategy_candidate",
        objective_profile="Balanced",
        explainability=exp,
        related_opportunities=("opp-1", "opp-2"),
        confidence=0.70,
        expected_gain=0.60,
        versions={"strategy_version_id": ev.strategy_version_id},
    )
    defaults.update(kw)
    return DecisionCandidate(**defaults)


def _record(record_id=None, status="Proposed", versions=None, explainability=None) -> Mock:
    r = Mock()
    r.id = record_id or uuid.uuid4()
    r.status = status
    r.versions = versions or {"strategy_version_id": "sv-1"}
    r.explainability = explainability or {"reasons": ["reason"]}
    return r


def _service(
    candidates_repo=None,
    transitions_repo=None,
    bus=None,
    scoring_svc=None,
) -> Phase5DecisionService:
    return Phase5DecisionService(
        decision_candidates_repository=candidates_repo or Mock(),
        decision_scoring_service=scoring_svc or _scoring_svc(),
        explainability_repository=Mock(),
        event_bus=bus or Mock(),
        decision_transitions_repository=transitions_repo or Mock(),
    )


# ================================================================== 1. Lifecycle transition validation

_VALID = [
    ("Proposed",  "Approved"),
    ("Proposed",  "Rejected"),
    ("Approved",  "Scheduled"),
    ("Approved",  "Cancelled"),
    ("Scheduled", "Executed"),
    ("Scheduled", "Cancelled"),
    ("Scheduled", "Expired"),
]

_INVALID = [
    ("Proposed",  "Scheduled"),
    ("Proposed",  "Executed"),
    ("Proposed",  "Cancelled"),
    ("Proposed",  "Expired"),
    ("Approved",  "Rejected"),
    ("Approved",  "Executed"),
    ("Rejected",  "Approved"),
    ("Rejected",  "Scheduled"),
    ("Executed",  "Cancelled"),
    ("Executed",  "Expired"),
    ("Cancelled", "Scheduled"),
    ("Expired",   "Executed"),
    ("Expired",   "Approved"),
]


@pytest.mark.parametrize("from_s,to_s", _VALID)
def test_valid_transitions_are_allowed(from_s, to_s):
    assert _scoring_svc().validate_transition(from_s, to_s) is True


@pytest.mark.parametrize("from_s,to_s", _INVALID)
def test_invalid_transitions_are_rejected(from_s, to_s):
    assert _scoring_svc().validate_transition(from_s, to_s) is False


def test_all_terminal_statuses_have_no_outgoing_transitions():
    for terminal in ("Rejected", "Executed", "Cancelled", "Expired"):
        assert ALLOWED_TRANSITIONS[terminal] == []


# ================================================================== 2. schedule/execute/cancel/expire

def _candidates_repo_for(record):
    repo = Mock()
    repo.get_by_id.return_value = record

    def _update(decision_candidate_id, status, decided_reason=None, decided_by="system", decided_at=None):
        updated = Mock()
        updated.id = record.id
        updated.status = status
        updated.versions = record.versions
        updated.explainability = record.explainability
        return updated

    repo.update_status.side_effect = _update
    return repo


def test_schedule_persists_transition_and_emits_event():
    dec_id = uuid.uuid4()
    rec = _record(dec_id, status="Approved")
    candidates_repo = _candidates_repo_for(rec)
    transitions_repo = Mock()
    bus = Mock()

    svc = _service(candidates_repo, transitions_repo, bus)
    result = svc.schedule(dec_id, reason="time to run", actor="planner")

    # DB side-effects
    candidates_repo.update_status.assert_called_once()
    transitions_repo.create.assert_called_once()

    kw = transitions_repo.create.call_args.kwargs
    assert kw["previous_status"] == "Approved"
    assert kw["new_status"]      == "Scheduled"
    assert kw["transition_reason"] == "time to run"
    assert kw["actor"] == "planner"
    assert "versions" in kw
    assert "explainability_snapshot" in kw
    assert "transition_time" in kw

    # Event
    event = bus.publish.call_args[0][0]
    assert isinstance(event, DecisionScheduled)
    assert event.decision_candidate_id == dec_id
    assert event.reason == "time to run"


def test_execute_after_schedule():
    dec_id = uuid.uuid4()
    rec = _record(dec_id, status="Scheduled")
    bus = Mock()
    svc = _service(_candidates_repo_for(rec), Mock(), bus)
    svc.execute(dec_id, reason="run now")
    assert isinstance(bus.publish.call_args[0][0], DecisionExecuted)


def test_cancel_from_approved():
    dec_id = uuid.uuid4()
    rec = _record(dec_id, status="Approved")
    bus = Mock()
    svc = _service(_candidates_repo_for(rec), Mock(), bus)
    svc.cancel(dec_id, reason="plan changed")
    assert isinstance(bus.publish.call_args[0][0], DecisionCancelled)


def test_cancel_from_scheduled():
    dec_id = uuid.uuid4()
    rec = _record(dec_id, status="Scheduled")
    bus = Mock()
    svc = _service(_candidates_repo_for(rec), Mock(), bus)
    svc.cancel(dec_id, reason="plan changed")
    assert isinstance(bus.publish.call_args[0][0], DecisionCancelled)


def test_expire_from_scheduled():
    dec_id = uuid.uuid4()
    rec = _record(dec_id, status="Scheduled")
    bus = Mock()
    svc = _service(_candidates_repo_for(rec), Mock(), bus)
    svc.expire(dec_id, reason="window passed")
    assert isinstance(bus.publish.call_args[0][0], DecisionExpired)


def test_approve_publishes_approved_event():
    dec_id = uuid.uuid4()
    rec = _record(dec_id, status="Proposed")
    bus = Mock()
    svc = _service(_candidates_repo_for(rec), Mock(), bus)
    svc.approve(dec_id, reason="looks good")
    assert isinstance(bus.publish.call_args[0][0], DecisionCandidateApproved)


def test_reject_publishes_rejected_event():
    dec_id = uuid.uuid4()
    rec = _record(dec_id, status="Proposed")
    bus = Mock()
    svc = _service(_candidates_repo_for(rec), Mock(), bus)
    svc.reject(dec_id, reason="too risky")
    assert isinstance(bus.publish.call_args[0][0], DecisionCandidateRejected)


# ================================================================== 3. Illegal transition — no side-effects

def test_illegal_transition_raises_and_has_no_side_effects():
    dec_id = uuid.uuid4()
    rec = _record(dec_id, status="Proposed")
    candidates_repo = _candidates_repo_for(rec)
    transitions_repo = Mock()
    bus = Mock()

    svc = _service(candidates_repo, transitions_repo, bus)
    with pytest.raises(ValueError, match="Invalid decision lifecycle transition"):
        svc.schedule(dec_id)  # Proposed -> Scheduled is illegal

    candidates_repo.update_status.assert_not_called()
    transitions_repo.create.assert_not_called()
    bus.publish.assert_not_called()


def test_missing_candidate_raises_value_error():
    repo = Mock()
    repo.get_by_id.return_value = None
    svc = _service(repo)
    with pytest.raises(ValueError, match="not found"):
        svc.approve(uuid.uuid4())


def test_terminal_status_raises_on_further_transition():
    for terminal in ("Rejected", "Executed", "Cancelled", "Expired"):
        dec_id = uuid.uuid4()
        rec = _record(dec_id, status=terminal)
        transitions_repo = Mock()
        bus = Mock()
        svc = _service(_candidates_repo_for(rec), transitions_repo, bus)
        with pytest.raises(ValueError):
            svc.approve(dec_id)
        transitions_repo.create.assert_not_called()
        bus.publish.assert_not_called()


# ================================================================== 4. Explainability

def test_explainability_to_dict_contains_required_fields():
    c = _candidate()
    d = c.explainability.to_dict()

    assert "reasons" in d and d["reasons"]
    assert "evidence" in d
    ev = d["evidence"]
    assert ev["strategy_candidate_id"]
    assert ev["strategy_version_id"]
    assert ev["category"] == "engagement"
    assert ev["hook_type"] == "question"
    assert "confidence" in d


def test_candidate_versions_link_to_strategy():
    c = _candidate()
    assert "strategy_version_id" in c.versions
    assert c.versions["strategy_version_id"] == c.explainability.evidence.strategy_version_id


def test_candidate_related_opportunities_present():
    c = _candidate()
    assert len(c.related_opportunities) > 0


def test_scoring_embeds_applied_weights_in_score():
    svc = _scoring_svc()
    c = _candidate(confidence=1.0, expected_gain=1.0, related_opportunities=("opp-1", "opp-2", "opp-3"))
    scored = svc.score(c, profile="Balanced")
    # With full confidence + gain and low risk, score must be positive
    assert scored.decision_score > 0.0
    assert scored.scoring_version == DecisionScoringService.SCORING_VERSION


# ================================================================== 5. Fingerprint / Replay determinism

def _fingerprinter() -> Phase5DecisionService:
    return Phase5DecisionService(
        decision_candidates_repository=Mock(),
        decision_scoring_service=Mock(),
        explainability_repository=Mock(),
        event_bus=Mock(),
        decision_transitions_repository=Mock(),
    )


def test_identical_candidates_produce_identical_fingerprints():
    svc = _fingerprinter()
    ev = _evidence(strategy_version_id="sv-fixed", strategy_candidate_id="sc-fixed")
    exp = DecisionExplainability(evidence=ev, confidence=0.7)

    c1 = DecisionCandidate(
        decision_type="execute_strategy_candidate",
        objective_profile="Balanced",
        explainability=exp,
        related_opportunities=("opp-1", "opp-2"),
    )
    c2 = DecisionCandidate(
        decision_type="execute_strategy_candidate",
        objective_profile="Balanced",
        explainability=exp,
        related_opportunities=("opp-2", "opp-1"),  # order should not matter
    )

    assert svc._compute_fingerprints(c1) == svc._compute_fingerprints(c2)


def test_different_strategy_candidates_produce_different_fingerprints():
    svc = _fingerprinter()
    ev1 = _evidence(strategy_version_id="sv-1", strategy_candidate_id="sc-A")
    ev2 = _evidence(strategy_version_id="sv-1", strategy_candidate_id="sc-B")

    c1 = DecisionCandidate(
        "execute_strategy_candidate", "Balanced",
        DecisionExplainability(evidence=ev1),
    )
    c2 = DecisionCandidate(
        "execute_strategy_candidate", "Balanced",
        DecisionExplainability(evidence=ev2),
    )

    fp1 = svc._compute_fingerprints(c1)
    fp2 = svc._compute_fingerprints(c2)
    assert fp1["fingerprint"] != fp2["fingerprint"]


def test_fingerprint_fields_all_present():
    svc = _fingerprinter()
    c = _candidate()
    fp = svc._compute_fingerprints(c)
    for key in ("structural_fingerprint", "feature_fingerprint", "fingerprint_hash", "fingerprint"):
        assert key in fp and fp[key], f"missing or empty: {key}"


def test_fingerprints_are_stable_across_multiple_calls():
    svc = _fingerprinter()
    c = _candidate()
    results = [svc._compute_fingerprints(c) for _ in range(10)]
    first = results[0]
    assert all(r == first for r in results[1:]), "fingerprints must be deterministic"


# ================================================================== 6. score_batch determinism

def test_score_batch_order_is_deterministic():
    svc = _scoring_svc()
    candidates = [
        _candidate(decision_type="z_type", confidence=0.5, expected_gain=0.4),
        _candidate(decision_type="a_type", confidence=0.9, expected_gain=0.9),
        _candidate(decision_type="m_type", confidence=0.7, expected_gain=0.6),
    ]

    batch_1 = svc.score_batch(candidates, profile="Balanced")
    batch_2 = svc.score_batch(candidates, profile="Balanced")

    assert [c.decision_type for c in batch_1] == [c.decision_type for c in batch_2]
    # Must be sorted highest score first
    scores = [c.decision_score for c in batch_1]
    assert scores == sorted(scores, reverse=True)


def test_score_batch_tiebreak_by_decision_type():
    """When scores are equal the tiebreak is decision_type alphabetically."""
    svc = _scoring_svc()
    # Same inputs → same score; distinguish only by decision_type
    ev = _evidence(strategy_version_id="sv-1", strategy_candidate_id="sc-1",
                   source_confidence=0.5, source_expected_success=0.5)
    exp = DecisionExplainability(evidence=ev, confidence=0.5)
    ca = DecisionCandidate("z_action", "Balanced", exp,
                           confidence=0.5, expected_gain=0.5, related_opportunities=("x",))
    cb = DecisionCandidate("a_action", "Balanced", exp,
                           confidence=0.5, expected_gain=0.5, related_opportunities=("x",))

    result = svc.score_batch([ca, cb], profile="Balanced")
    # Equal scores → "a_action" < "z_action"
    assert result[0].decision_type == "a_action"
    assert result[1].decision_type == "z_action"
