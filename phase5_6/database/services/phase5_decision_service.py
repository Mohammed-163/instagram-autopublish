from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from core.container import container
from core.events import (
    DecisionCandidateApproved,
    DecisionCandidateProposed,
    DecisionCandidateRejected,
    DecisionCancelled,
    DecisionExecuted,
    DecisionExpired,
    DecisionScheduled,
)
from engines.decision.decision_candidate import DecisionCandidate

logger = logging.getLogger(__name__)


class Phase5DecisionService:
    """Phase 5 (Part 1) — Decision Layer Foundation.

    Responsibilities ONLY:
    - fingerprint generation (the ONLY place fingerprints for decisions
      are computed)
    - lifecycle validation (delegates the transition rules themselves to
      DecisionScoringService.validate_transition, but is the only caller
      allowed to apply a transition)
    - persistence (the only service that talks to DecisionCandidatesRepository)
    - explainability storage (via the shared ExplainabilityRepository)

    This service never scores a candidate itself — scoring is delegated
    entirely to DecisionScoringService, the single source of truth for
    decision scores.
    """

    FINGERPRINT_VERSION = "1.0.0"

    def __init__(
        self,
        decision_candidates_repository: Any = None,
        decision_scoring_service: Any = None,
        explainability_repository: Any = None,
        event_bus: Any = None,
        decision_transitions_repository: Any = None,
    ) -> None:
        # Each dependency is resolved lazily (see properties below) rather
        # than eagerly here, because this singleton is constructed during
        # container bring-up, before every name it needs is necessarily
        # registered yet.
        self._decision_candidates_repository_override = decision_candidates_repository
        self._decision_scoring_service_override = decision_scoring_service
        self._explainability_repository_override = explainability_repository
        self._event_bus_override = event_bus
        self._decision_transitions_repository_override = decision_transitions_repository
        self._cache: Dict[str, Any] = {}

    def _resolve(self, override_attr: str, cache_key: str, container_name: str) -> Any:
        override = getattr(self, override_attr)
        if override is not None:
            return override
        if cache_key not in self._cache:
            self._cache[cache_key] = container.resolve(container_name)
        return self._cache[cache_key]

    @property
    def decision_candidates_repository(self) -> Any:
        return self._resolve(
            "_decision_candidates_repository_override", "decision_candidates_repository", "decision_candidates_repository"
        )

    @property
    def decision_scoring_service(self) -> Any:
        return self._resolve(
            "_decision_scoring_service_override", "decision_scoring_service", "decision_scoring_service"
        )

    @property
    def explainability_repository(self) -> Any:
        return self._resolve(
            "_explainability_repository_override", "explainability_repository", "explainability_repository"
        )

    @property
    def event_bus(self) -> Any:
        return self._resolve("_event_bus_override", "event_bus", "event_bus")

    @property
    def decision_transitions_repository(self) -> Any:
        return self._resolve(
            "_decision_transitions_repository_override",
            "decision_transitions_repository",
            "decision_transitions_repository",
        )

    # ------------------------------------------------------------------ fingerprinting
    def _compute_fingerprints(self, candidate: DecisionCandidate) -> Dict[str, str]:
        """Compute deterministic fingerprints for deduplication and analysis.
        Fingerprint generation for decisions exists ONLY here."""
        evidence = candidate.explainability.evidence if candidate.explainability else None

        structural_data = {
            "decision_type": candidate.decision_type,
            "objective_profile": candidate.objective_profile,
            "strategy_candidate_id": evidence.strategy_candidate_id if evidence else "",
            "version": self.FINGERPRINT_VERSION,
        }
        feature_data = {
            "related_opportunities": sorted(candidate.related_opportunities),
            "hook_type": evidence.hook_type if evidence else "",
            "category": evidence.category if evidence else "",
        }

        struct_raw = json.dumps(structural_data, sort_keys=True)
        feat_raw = json.dumps(feature_data, sort_keys=True)

        structural = hashlib.sha256(struct_raw.encode()).hexdigest()[:16]
        feature = hashlib.sha256(feat_raw.encode()).hexdigest()[:16]

        combined = json.dumps({"structural": structural, "feature": feature}, sort_keys=True)
        fingerprint_hash = hashlib.sha256(combined.encode()).hexdigest()[:16]

        return {
            "structural_fingerprint": structural,
            "feature_fingerprint": feature,
            "fingerprint_hash": fingerprint_hash,
            "fingerprint": fingerprint_hash,  # hash doubles as the primary fingerprint
        }

    # ------------------------------------------------------------------ persistence
    def persist_candidate(self, candidate: DecisionCandidate, scoring_profile: str = "Balanced") -> Any:
        """Score and persist a DecisionCandidate. Deduplicates by fingerprint."""
        fingerprints = self._compute_fingerprints(candidate)
        fingerprint = fingerprints["fingerprint"]

        existing = self.decision_candidates_repository.get_by_fingerprint(fingerprint)
        if existing:
            logger.info("Decision candidate already exists with fingerprint %s, skipping.", fingerprint)
            return existing

        # Scoring is the exclusive responsibility of DecisionScoringService.
        scored = self.decision_scoring_service.score(candidate, profile=scoring_profile)
        now = datetime.now(timezone.utc)
        evidence = scored.explainability.evidence if scored.explainability else None

        record = self.decision_candidates_repository.create(
            strategy_version_id=evidence.strategy_version_id if evidence else None,
            strategy_candidate_id=evidence.strategy_candidate_id if evidence else None,
            decision_type=scored.decision_type,
            objective_profile=scored.objective_profile,
            status="Proposed",
            confidence=float(scored.confidence),
            expected_gain=float(scored.expected_gain),
            risk=float(scored.risk or 0.0),
            decision_score=float(scored.decision_score or 0.0),
            related_opportunities=list(scored.related_opportunities),
            explainability=scored.explainability.to_dict() if scored.explainability else {},
            versions=dict(scored.versions),
            metadata_=dict(scored.metadata),
            scoring_version=scored.scoring_version,
            fingerprint=fingerprints["fingerprint"],
            structural_fingerprint=fingerprints["structural_fingerprint"],
            feature_fingerprint=fingerprints["feature_fingerprint"],
            fingerprint_hash=fingerprints["fingerprint_hash"],
            fingerprint_version=scored.fingerprint_version,
            proposed_at=now,
            updated_at=now,
        )

        # Explainability storage — shared ExplainabilityRepository, keyed by
        # (subject_type, subject_id) same as every other explainable subject.
        self.explainability_repository.create(
            subject_type="decision_candidate",
            subject_id=record.id,
            explanation="; ".join(scored.explainability.reasons) if scored.explainability else "",
            factors=scored.explainability.to_dict() if scored.explainability else {},
        )

        self.decision_transitions_repository.create(
            decision_candidate_id=str(record.id),
            previous_status=None,
            new_status="Proposed",
            transition_reason="Decision candidate proposed by Phase5DecisionEngine.",
            actor="system",
            versions=dict(scored.versions),
            explainability_snapshot=scored.explainability.to_dict() if scored.explainability else {},
            transition_time=now,
        )

        self.event_bus.publish(
            DecisionCandidateProposed(
                decision_candidate_id=record.id,
                strategy_version_id=evidence.strategy_version_id if evidence else None,
                decision_type=record.decision_type,
                objective_profile=record.objective_profile,
                decision_score=float(record.decision_score),
                fingerprint=fingerprint,
            )
        )

        return record

    # ------------------------------------------------------------------ lifecycle transitions
    # Full lifecycle: Proposed -> Approved -> Scheduled -> Executed
    #                          -> Rejected                (terminal)
    #              Approved/Scheduled -> Cancelled          (terminal)
    #                          Scheduled -> Expired          (terminal)
    # Every transition is validated against DecisionScoringService's
    # ALLOWED_TRANSITIONS map and persisted through update_status — no
    # direct object mutation ever happens here or anywhere else.
    def approve(self, decision_candidate_id: Any, reason: str = "", actor: str = "system") -> Any:
        """Transition a decision candidate Proposed -> Approved."""
        return self._transition(decision_candidate_id, "Approved", reason, actor, DecisionCandidateApproved)

    def reject(self, decision_candidate_id: Any, reason: str = "", actor: str = "system") -> Any:
        """Transition a decision candidate Proposed -> Rejected."""
        return self._transition(decision_candidate_id, "Rejected", reason, actor, DecisionCandidateRejected)

    def schedule(self, decision_candidate_id: Any, reason: str = "", actor: str = "system") -> Any:
        """Transition a decision candidate Approved -> Scheduled."""
        return self._transition(decision_candidate_id, "Scheduled", reason, actor, DecisionScheduled)

    def execute(self, decision_candidate_id: Any, reason: str = "", actor: str = "system") -> Any:
        """Transition a decision candidate Scheduled -> Executed."""
        return self._transition(decision_candidate_id, "Executed", reason, actor, DecisionExecuted)

    def cancel(self, decision_candidate_id: Any, reason: str = "", actor: str = "system") -> Any:
        """Transition a decision candidate Approved/Scheduled -> Cancelled."""
        return self._transition(decision_candidate_id, "Cancelled", reason, actor, DecisionCancelled)

    def expire(self, decision_candidate_id: Any, reason: str = "", actor: str = "system") -> Any:
        """Transition a decision candidate Scheduled -> Expired."""
        return self._transition(decision_candidate_id, "Expired", reason, actor, DecisionExpired)

    def _transition(
        self,
        decision_candidate_id: Any,
        to_status: str,
        reason: str,
        actor: str,
        event_cls: Any,
    ) -> Any:
        record = self.decision_candidates_repository.get_by_id(decision_candidate_id)
        if not record:
            raise ValueError(f"DecisionCandidate {decision_candidate_id} not found.")

        from_status = record.status
        if not self.decision_scoring_service.validate_transition(from_status, to_status):
            raise ValueError(f"Invalid decision lifecycle transition from '{from_status}' to '{to_status}'.")

        now = datetime.now(timezone.utc)
        updated = self.decision_candidates_repository.update_status(
            decision_candidate_id, to_status, decided_reason=reason, decided_by=actor, decided_at=now
        )

        # Persist the transition — the only place decision transitions are
        # ever recorded. Never a direct mutation of the candidate record.
        self.decision_transitions_repository.create(
            decision_candidate_id=str(updated.id),
            previous_status=from_status,
            new_status=to_status,
            transition_reason=reason,
            actor=actor,
            versions=dict(updated.versions or {}),
            explainability_snapshot=dict(updated.explainability or {}),
            transition_time=now,
        )

        self.event_bus.publish(
            event_cls(decision_candidate_id=updated.id, reason=reason, actor=actor)
        )

        return updated

    # ------------------------------------------------------------------ history
    def get_transition_history(self, decision_candidate_id: Any) -> Any:
        """Return the full, chronologically ordered transition history for a decision."""
        return self.decision_transitions_repository.get_by_decision(decision_candidate_id)

    # ------------------------------------------------------------------ reads
    def get_by_status(self, status: str) -> Any:
        return self.decision_candidates_repository.get_by_status(status)

    def get_by_strategy_version(self, strategy_version_id: Any) -> Any:
        return self.decision_candidates_repository.get_by_strategy_version(strategy_version_id)


phase5_decision_service = Phase5DecisionService()
