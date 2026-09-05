"""
Phase6ExecutionService — Phase 6 Part 1.

Responsibilities (and ONLY these):
  - create_execution()  : create a new ExecutionRecord in status 'Pending'
                          and publish ExecutionPending
  - schedule()          : Pending   → Scheduled  → publish ExecutionScheduled
  - start()             : Scheduled → Running    → publish ExecutionStarted
  - complete()          : Running   → Completed  → publish ExecutionCompleted
  - fail()              : Running   → Failed     → publish ExecutionFailed
  - cancel()            : Pending|Scheduled → Cancelled → publish ExecutionCancelled
  - expire()            : Pending|Scheduled → Expired   → publish ExecutionExpired

Every method follows the invariant:
  Validate → Update Status → Persist Transition History → Publish Event

This service is the ONLY layer that writes to ExecutionRepository and
ExecutionTransitionRepository.  No direct DB access is allowed anywhere else
in the execution layer.

Architecture rule: Service → Repository only. Engine → Service only.

Determinism rules:
  - All fingerprint dicts use sort_keys=True.
  - All numeric thresholds come from SettingsService.
  - No Business Values embedded in code.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.container import container
from core.events import (
    ExecutionPending,
    ExecutionScheduled,
    ExecutionStarted,
    ExecutionCompleted,
    ExecutionFailed,
    ExecutionCancelled,
    ExecutionExpired,
)

logger = logging.getLogger(__name__)

FINGERPRINT_VERSION = "1.0.0"


class Phase6ExecutionService:
    """Lifecycle manager for ExecutionRecord persistence.

    All dependencies are injected lazily so this singleton can be constructed
    before the container is fully populated (same pattern as Phase5DecisionService).
    """

    def __init__(
        self,
        execution_repository: Any = None,
        execution_transition_repository: Any = None,
        execution_validation_service: Any = None,
        event_bus: Any = None,
    ) -> None:
        self._execution_repository_override = execution_repository
        self._execution_transition_repository_override = execution_transition_repository
        self._execution_validation_service_override = execution_validation_service
        self._event_bus_override = event_bus
        self._cache: Dict[str, Any] = {}

    # ------------------------------------------------------------------ lazy resolvers

    def _resolve(self, override_attr: str, cache_key: str, container_name: str) -> Any:
        override = getattr(self, override_attr)
        if override is not None:
            return override
        if cache_key not in self._cache:
            self._cache[cache_key] = container.resolve(container_name)
        return self._cache[cache_key]

    @property
    def _repo(self) -> Any:
        return self._resolve(
            "_execution_repository_override",
            "execution_repository",
            "execution_repository",
        )

    @property
    def _transition_repo(self) -> Any:
        return self._resolve(
            "_execution_transition_repository_override",
            "execution_transition_repository",
            "execution_transition_repository",
        )

    @property
    def _validation(self) -> Any:
        return self._resolve(
            "_execution_validation_service_override",
            "execution_validation_service",
            "execution_validation_service",
        )

    @property
    def _bus(self) -> Any:
        return self._resolve("_event_bus_override", "event_bus", "event_bus")

    # ------------------------------------------------------------------ fingerprinting

    def _compute_fingerprint(
        self,
        decision_candidate_id: Optional[str],
        execution_type: str,
        objective_profile: str,
    ) -> str:
        """Deterministic fingerprint for deduplication.

        Determinism rule: sort_keys=True ensures identical dicts always hash the same.
        """
        data = {
            "decision_candidate_id": decision_candidate_id or "",
            "execution_type": execution_type,
            "objective_profile": objective_profile,
            "version": FINGERPRINT_VERSION,
        }
        raw = json.dumps(data, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    # ------------------------------------------------------------------ public API

    def create_execution(
        self,
        *,
        decision_candidate_id: Optional[str],
        execution_type: str,
        objective_profile: str = "",
        metadata_: Optional[dict] = None,
        versions: Optional[dict] = None,
        explainability: Optional[dict] = None,
    ) -> Any:
        """Create a new ExecutionRecord in status 'Pending' and publish ExecutionPending.

        This is the ONLY entry point into the Execution lifecycle.
        No execution logic is performed here — only persistence and event emission.
        """
        fingerprint = self._compute_fingerprint(
            decision_candidate_id, execution_type, objective_profile
        )

        # Deduplication guard (deterministic fingerprint prevents duplicate executions)
        existing = self._repo.get_by_fingerprint(fingerprint)
        if existing:
            logger.info(
                "[Phase6ExecutionService] Execution already exists for fingerprint %s, skipping.",
                fingerprint,
            )
            return existing

        record = self._repo.create_execution(
            decision_candidate_id=decision_candidate_id,
            execution_type=execution_type,
            objective_profile=objective_profile,
            fingerprint=fingerprint,
            fingerprint_version=FINGERPRINT_VERSION,
            metadata_=metadata_ or {},
            versions=versions or {},
            explainability=explainability or {},
        )

        # Persist initial transition: None → Pending
        self._transition_repo.append(
            execution_id=str(record.id),
            from_status=None,
            to_status="Pending",
            reason="Execution created from approved decision candidate.",
            actor="system",
            versions={"fingerprint_version": FINGERPRINT_VERSION},
        )

        # Publish ExecutionPending (the only event emitted by this method)
        self._bus.publish(
            ExecutionPending(
                execution_id=record.id,
                decision_candidate_id=decision_candidate_id,
                execution_type=execution_type,
                objective_profile=objective_profile,
                fingerprint=fingerprint,
            )
        )

        return record

    # ------------------------------------------------------------------ lifecycle transitions

    def schedule(self, execution_id: Any, *, reason: str = "", actor: str = "system") -> Any:
        """Transition Pending → Scheduled."""
        return self._transition(
            execution_id=execution_id,
            to_status="Scheduled",
            reason=reason,
            actor=actor,
            event_factory=lambda record: ExecutionScheduled(
                execution_id=record.id,
                decision_candidate_id=record.decision_candidate_id,
                execution_type=record.execution_type,
            ),
            extra_fields={"scheduled_at": datetime.now(timezone.utc)},
        )

    def start(self, execution_id: Any, *, reason: str = "", actor: str = "system") -> Any:
        """Transition Scheduled → Running."""
        return self._transition(
            execution_id=execution_id,
            to_status="Running",
            reason=reason,
            actor=actor,
            event_factory=lambda record: ExecutionStarted(
                execution_id=record.id,
                decision_candidate_id=record.decision_candidate_id,
                execution_type=record.execution_type,
            ),
            extra_fields={"started_at": datetime.now(timezone.utc)},
        )

    def complete(
        self,
        execution_id: Any,
        *,
        result: Optional[dict] = None,
        reason: str = "",
        actor: str = "system",
    ) -> Any:
        """Transition Running → Completed."""
        return self._transition(
            execution_id=execution_id,
            to_status="Completed",
            reason=reason,
            actor=actor,
            event_factory=lambda record: ExecutionCompleted(
                execution_id=record.id,
                decision_candidate_id=record.decision_candidate_id,
                execution_type=record.execution_type,
                result=result or {},
            ),
            extra_fields={
                "completed_at": datetime.now(timezone.utc),
                "result": result or {},
            },
        )

    def fail(
        self,
        execution_id: Any,
        *,
        failure_reason: str = "",
        reason: str = "",
        actor: str = "system",
    ) -> Any:
        """Transition Running → Failed."""
        return self._transition(
            execution_id=execution_id,
            to_status="Failed",
            reason=reason or failure_reason,
            actor=actor,
            event_factory=lambda record: ExecutionFailed(
                execution_id=record.id,
                decision_candidate_id=record.decision_candidate_id,
                execution_type=record.execution_type,
                failure_reason=failure_reason,
            ),
            extra_fields={
                "completed_at": datetime.now(timezone.utc),
                "failure_reason": failure_reason,
            },
        )

    def cancel(
        self,
        execution_id: Any,
        *,
        reason: str = "",
        actor: str = "system",
    ) -> Any:
        """Transition Pending|Scheduled → Cancelled."""
        return self._transition(
            execution_id=execution_id,
            to_status="Cancelled",
            reason=reason,
            actor=actor,
            event_factory=lambda record: ExecutionCancelled(
                execution_id=record.id,
                decision_candidate_id=record.decision_candidate_id,
                execution_type=record.execution_type,
                reason=reason,
            ),
            extra_fields={"completed_at": datetime.now(timezone.utc)},
        )

    def expire(
        self,
        execution_id: Any,
        *,
        reason: str = "",
        actor: str = "system",
    ) -> Any:
        """Transition Pending|Scheduled → Expired."""
        return self._transition(
            execution_id=execution_id,
            to_status="Expired",
            reason=reason,
            actor=actor,
            event_factory=lambda record: ExecutionExpired(
                execution_id=record.id,
                decision_candidate_id=record.decision_candidate_id,
                execution_type=record.execution_type,
                reason=reason,
            ),
            extra_fields={"expired_at": datetime.now(timezone.utc)},
        )

    # ------------------------------------------------------------------ internal

    def _transition(
        self,
        *,
        execution_id: Any,
        to_status: str,
        reason: str,
        actor: str,
        event_factory: Any,
        extra_fields: Optional[dict] = None,
    ) -> Any:
        """Shared implementation: Validate → Update → Persist Transition → Publish."""
        record = self._repo.get_by_id(execution_id)
        if record is None:
            raise ValueError(f"ExecutionRecord {execution_id} not found.")

        if not self._validation.validate_execution_transition(record.status, to_status):
            raise ValueError(
                f"Invalid execution lifecycle transition from '{record.status}' to '{to_status}'."
            )

        # Build update fields; updated_at is always set by the repository
        fields: dict = {"status": to_status, **(extra_fields or {})}
        updated = self._repo.update(execution_id, **fields)
        if updated is None:
            raise ValueError(f"Failed to update ExecutionRecord {execution_id}.")

        # Persist transition history with full explainability fields
        self._transition_repo.append(
            execution_id=str(updated.id),
            from_status=record.status,
            to_status=to_status,
            reason=reason,
            actor=actor,
            versions={"fingerprint_version": updated.fingerprint_version or FINGERPRINT_VERSION},
        )

        self._bus.publish(event_factory(updated))

        return updated

    # ------------------------------------------------------------------ reads

    def get_by_status(self, status: str) -> Any:
        return self._repo.get_by_status(status)

    def get_history(self, execution_id: Any) -> Any:
        return self._transition_repo.get_history(str(execution_id))

    def get_by_decision_candidate(self, decision_candidate_id: str) -> Any:
        return self._repo.get_by_decision_candidate(decision_candidate_id)


# Module-level singleton consumed by container.py.
phase6_execution_service = Phase6ExecutionService()
