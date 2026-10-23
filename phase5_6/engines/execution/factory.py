"""
ExecutionPlanFactory — Phase 6 Part 2 & Part 3 (Execution Factory).

Single responsibility: convert an approved DecisionCandidate event
OR an existing ExecutionRecord into a fully-formed, immutable ExecutionPlan.

Architectural rules enforced here:
  - No repository access.
  - No API calls.
  - Fully deterministic output for identical inputs.
  - sort_keys=True on all JSON operations.
  - No random, no uuid in fingerprints, no timestamps in fingerprints.
  - All numeric thresholds come from SettingsService via settings dict.
  - No Business Values embedded in code.

Explainability invariant: every produced ExecutionPlan must have
  source_decision, source_strategy, execution_profile, platform,
  ordered_steps (summary), versions, creation_reason.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, Optional, Tuple

from engines.execution.execution_plan import (
    ExecutionPlan,
    ExecutionStep,
    RetryPolicy,
)

logger = logging.getLogger(__name__)

FACTORY_VERSION = "1.0.0"

# Canonical ordered steps for every platform execution.
# The order is deterministic and platform-agnostic at the factory level.
# Adapters receive these steps via the plan; no factory-level branching.
_DEFAULT_STEP_SEQUENCE: Tuple[Tuple[int, str, str], ...] = (
    (1, "validate", "platform_op"),
    (2, "prepare",  "platform_op"),
    (3, "execute",  "platform_op"),
    (4, "cleanup",  "platform_op"),
)


def _build_plan_id(
    decision_id: str,
    execution_id: str,
    target_platform: str,
    execution_profile: str,
) -> str:
    """Deterministic plan identifier.

    Rules: sort_keys=True, no timestamps, no random, no uuid.
    """
    data = {
        "decision_id": decision_id,
        "execution_id": execution_id,
        "execution_profile": execution_profile,
        "factory_version": FACTORY_VERSION,
        "target_platform": target_platform,
    }
    raw = json.dumps(data, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _build_steps(
    step_parameters: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Tuple[ExecutionStep, ...]:
    """Build the deterministically ordered step sequence.

    *step_parameters* is an optional dict keyed by step_name that merges
    plan-specific parameters into each step without changing the order.
    The output tuple is always sorted by (order, step_name).
    """
    params = step_parameters or {}
    steps = tuple(
        ExecutionStep(
            order=order,
            step_name=step_name,
            step_type=step_type,
            parameters=dict(sorted(params.get(step_name, {}).items())),  # sort_keys determinism
        )
        for order, step_name, step_type in sorted(  # deterministic by order
            _DEFAULT_STEP_SEQUENCE, key=lambda t: t[0]
        )
    )
    return steps


class ExecutionPlanFactory:
    """Converts approved decision data into an immutable ExecutionPlan.

    The factory is stateless — every call with the same inputs produces
    an identical ExecutionPlan (deterministic).

    Dependency: receives a settings dict from the caller (from SettingsService).
    The factory never calls SettingsService directly — the caller resolves
    settings and passes them in, preserving the Service → Repository chain.
    """

    FACTORY_NAME = "execution_plan_factory"
    FACTORY_VERSION = FACTORY_VERSION

    # ------------------------------------------------------------------ public API

    def build(
        self,
        *,
        execution_id: str,
        decision_id: str,
        target_platform: str,
        execution_profile: str,
        source_strategy: str = "",
        creation_reason: str = "Approved decision candidate converted to execution plan.",
        step_parameters: Optional[Dict[str, Dict[str, Any]]] = None,
        extra_versions: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> ExecutionPlan:
        """Build and return an immutable ExecutionPlan.

        All numeric values (timeout, retry) come from *settings*.
        No business values are embedded here.

        Args:
            execution_id     : ExecutionRecord.id this plan belongs to.
            decision_id      : Source DecisionCandidate.id.
            target_platform  : Platform key, e.g. "instagram", "youtube".
            execution_profile: Profile name, e.g. "growth", "engagement".
            source_strategy  : Strategy version / candidate ref for explainability.
            creation_reason  : Human-readable reason for this plan (explainability).
            step_parameters  : Optional per-step parameter overrides.
            extra_versions   : Additional version tags to embed in the plan.
            settings         : Dict from SettingsService["execution_layer"].
        """
        cfg = settings or {}

        plan_id = _build_plan_id(
            decision_id=decision_id,
            execution_id=execution_id,
            target_platform=target_platform,
            execution_profile=execution_profile,
        )

        steps = _build_steps(step_parameters)

        retry_policy = RetryPolicy(
            max_attempts=int(cfg.get("retry_max_attempts", 0)),
            backoff_seconds=int(cfg.get("retry_backoff_seconds", 0)),
            retry_on_statuses=tuple(
                sorted(cfg.get("retry_on_statuses", []))  # deterministic sort
            ),
        )

        timeout_seconds = int(cfg.get("execution_timeout_seconds", 0))

        versions: Dict[str, Any] = {
            "factory_version": self.FACTORY_VERSION,
            "factory_name": self.FACTORY_NAME,
        }
        if extra_versions:
            # Sort keys for determinism
            versions.update(dict(sorted(extra_versions.items())))

        explainability: Dict[str, Any] = {
            "source_decision": decision_id,
            "source_strategy": source_strategy,
            "execution_profile": execution_profile,
            "platform": target_platform,
            "ordered_steps": list(s.step_name for s in steps),  # already deterministic
            "versions": dict(sorted(versions.items())),          # sort_keys determinism
            "creation_reason": creation_reason,
        }

        plan = ExecutionPlan(
            execution_id=execution_id,
            decision_id=decision_id,
            plan_id=plan_id,
            target_platform=target_platform,
            execution_profile=execution_profile,
            ordered_steps=steps,
            retry_policy=retry_policy,
            timeout_seconds=timeout_seconds,
            explainability=explainability,
            versions=dict(sorted(versions.items())),
        )

        logger.info(
            "[ExecutionPlanFactory] Built plan_id=%s for execution_id=%s"
            " platform=%s profile=%s steps=%d",
            plan_id,
            execution_id,
            target_platform,
            execution_profile,
            plan.total_steps,
        )

        return plan

    def build_from_event(
        self,
        *,
        execution_id: str,
        decision_candidate_id: str,
        target_platform: str,
        objective_profile: str,
        actor: str = "system",
        reason: str = "",
        settings: Optional[Dict[str, Any]] = None,
    ) -> ExecutionPlan:
        """Convenience method: build an ExecutionPlan directly from event fields.

        Maps DecisionCandidateApproved event fields to build() parameters
        without the caller needing to know the internal mapping.
        """
        return self.build(
            execution_id=execution_id,
            decision_id=decision_candidate_id,
            target_platform=target_platform,
            execution_profile=objective_profile,
            source_strategy=f"decision_candidate:{decision_candidate_id}",
            creation_reason=(
                reason or f"ExecutionPlan created from approved decision candidate. Actor: {actor}."
            ),
            settings=settings,
            extra_versions={"actor": actor},
        )

    def build_from_execution_record(
        self,
        *,
        execution_record: Any,
        target_platform: str,
        settings: Optional[Dict[str, Any]] = None,
        step_parameters: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> ExecutionPlan:
        """Build an ExecutionPlan from an existing ExecutionRecord.

        No repository access — the caller passes the already-fetched record.
        Derives execution_profile from record.objective_profile.
        Derives decision_id from record.decision_candidate_id (or record.id as fallback).

        This method is the canonical way to build a plan when the orchestrator
        is triggered by a lifecycle event rather than a fresh decision approval.

        Args:
            execution_record : Fetched ExecutionRecord ORM object.
            target_platform  : Platform key, e.g. "youtube", "instagram".
            settings         : Dict from SettingsService["execution_layer"].
            step_parameters  : Optional per-step parameter overrides.
        """
        execution_id = str(execution_record.id)
        decision_id = str(
            execution_record.decision_candidate_id or execution_record.id
        )
        execution_profile = execution_record.objective_profile or ""
        explainability_src = dict(sorted((execution_record.explainability or {}).items()))
        versions_src = dict(sorted((execution_record.versions or {}).items()))

        creation_reason = (
            f"ExecutionPlan built from ExecutionRecord {execution_id} "
            f"(status={execution_record.status}, profile={execution_profile})."
        )

        return self.build(
            execution_id=execution_id,
            decision_id=decision_id,
            target_platform=target_platform,
            execution_profile=execution_profile,
            source_strategy=f"execution_record:{execution_id}",
            creation_reason=creation_reason,
            step_parameters=step_parameters,
            extra_versions=dict(sorted({
                **versions_src,
                "source_record_status": execution_record.status,
            }.items())),
            settings=settings,
        )


# Module-level singleton consumed by container.py
execution_plan_factory = ExecutionPlanFactory()
