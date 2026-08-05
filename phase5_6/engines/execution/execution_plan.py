"""
ExecutionPlan — Phase 6 Part 2 (Execution Orchestrator & Platform Abstraction).

Immutable domain model that carries all information needed to orchestrate
one execution attempt.  It is the ONLY object passed between:
  ExecutionPlanFactory → ExecutionOrchestrator → BaseExecutionAdapter

Architectural rules enforced here:
  - Fully immutable (frozen=True dataclass).
  - No repository access, no DB session, no SQL.
  - No random, no uuid in fingerprints, no timestamps in fingerprints.
  - All step ordering is deterministic (tuple, not list).
  - Fingerprint uses sort_keys=True.

Explainability fields required on every plan:
  source_decision, source_strategy, execution_profile, platform,
  ordered_steps, versions, creation_reason.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class RetryPolicy:
    """Immutable retry configuration.

    All values come from SettingsService — no magic numbers here.
    """
    max_attempts: int = 0          # 0 = no retry (value injected from settings)
    backoff_seconds: int = 0       # seconds between retries (from settings)
    retry_on_statuses: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ExecutionStep:
    """One logical step inside an ExecutionPlan.

    Immutable. Ordering is determined by the `order` field so that any
    sorted list of steps is always deterministic.
    """
    order: int                    # explicit position — not derived from list index
    step_name: str                # e.g. "validate", "prepare", "execute", "cleanup"
    step_type: str                # e.g. "platform_op", "check", "transform"
    parameters: Dict[str, Any] = field(default_factory=dict)
    depends_on: Tuple[str, ...] = field(default_factory=tuple)  # step_names this depends on

    def __post_init__(self) -> None:
        # Enforce immutable tuple types so callers can't pass mutable lists
        object.__setattr__(self, "depends_on", tuple(sorted(self.depends_on)))


@dataclass(frozen=True)
class ExecutionPlan:
    """Immutable, fully self-describing execution plan.

    Created by ExecutionPlanFactory from an approved DecisionCandidate.
    Consumed by ExecutionOrchestrator.
    Passed (read-only) to BaseExecutionAdapter.

    Explainability invariant: every plan must carry source_decision,
    source_strategy, execution_profile, platform, ordered_steps,
    versions, and creation_reason.
    """

    # Identity
    execution_id: str                      # links back to ExecutionRecord.id
    decision_id: str                       # source DecisionCandidate.id
    plan_id: str                           # deterministic fingerprint of this plan

    # Routing
    target_platform: str                   # e.g. "instagram", "youtube"
    execution_profile: str                 # e.g. "growth", "engagement"

    # Execution graph — immutable, deterministically ordered
    ordered_steps: Tuple[ExecutionStep, ...]

    # Policies (values from SettingsService, never hardcoded)
    retry_policy: RetryPolicy
    timeout_seconds: int                   # from SettingsService

    # Explainability (required — checked in __post_init__)
    explainability: Dict[str, Any]
    """Must include: source_decision, source_strategy, execution_profile,
    platform, ordered_steps summary, versions, creation_reason."""

    # Versioning
    versions: Dict[str, Any]

    # Audit
    created_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        # Enforce deterministic step ordering (sort by order, then step_name)
        sorted_steps = tuple(
            sorted(self.ordered_steps, key=lambda s: (s.order, s.step_name))
        )
        object.__setattr__(self, "ordered_steps", sorted_steps)

        # Validate required explainability keys
        required_keys = {
            "source_decision", "source_strategy", "execution_profile",
            "platform", "ordered_steps", "versions", "creation_reason",
        }
        missing = required_keys - set(self.explainability.keys())
        if missing:
            raise ValueError(
                f"ExecutionPlan.explainability is missing required keys: {sorted(missing)}"
            )

    # ------------------------------------------------------------------ helpers

    @property
    def step_names(self) -> Tuple[str, ...]:
        """Ordered step names — deterministic, stable tuple."""
        return tuple(s.step_name for s in self.ordered_steps)

    @property
    def total_steps(self) -> int:
        return len(self.ordered_steps)

    def to_fingerprint_dict(self) -> Dict[str, Any]:
        """Deterministic dict for hashing / deduplication.

        Rules: sort_keys=True, no timestamps, no uuids, no random.
        """
        return {
            "decision_id": self.decision_id,
            "execution_profile": self.execution_profile,
            "target_platform": self.target_platform,
            "step_names": list(self.step_names),   # already deterministically ordered
            "timeout_seconds": self.timeout_seconds,
            "retry_max_attempts": self.retry_policy.max_attempts,
        }

    def fingerprint_hash(self) -> str:
        """SHA-256 fingerprint of this plan (deterministic, sort_keys=True)."""
        raw = json.dumps(self.to_fingerprint_dict(), sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
