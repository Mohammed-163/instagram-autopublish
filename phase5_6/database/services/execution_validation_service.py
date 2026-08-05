"""
ExecutionValidationService — Phase 6 Part 1.

Single responsibility: validate_execution_transition().

No other business logic lives here.  Every lifecycle transition in
Phase6ExecutionService must pass through this service before the status
is applied.

Allowed transitions (8 only — all others are rejected):
  Pending   → Scheduled
  Scheduled → Running
  Running   → Completed
  Running   → Failed
  Pending   → Cancelled
  Scheduled → Cancelled
  Pending   → Expired
  Scheduled → Expired

Terminal statuses: Completed, Failed, Cancelled, Expired.
Any transition FROM a terminal status is always rejected.
"""
from __future__ import annotations

import logging
from typing import FrozenSet, Tuple

logger = logging.getLogger(__name__)

# Allowed (from_status, to_status) pairs — the complete, fixed transition graph.
# Order must be deterministic: frozenset guarantees no ordering dependency.
_ALLOWED_TRANSITIONS: FrozenSet[Tuple[str, str]] = frozenset(
    {
        ("Pending", "Scheduled"),
        ("Scheduled", "Running"),
        ("Running", "Completed"),
        ("Running", "Failed"),
        ("Pending", "Cancelled"),
        ("Scheduled", "Cancelled"),
        ("Pending", "Expired"),
        ("Scheduled", "Expired"),
    }
)

# Terminal statuses — no further transitions are permitted once reached.
_TERMINAL_STATUSES: FrozenSet[str] = frozenset(
    {"Completed", "Failed", "Cancelled", "Expired"}
)


class ExecutionValidationService:
    """Stateless validator for execution lifecycle transitions.

    Architecture rule: this service never raises — callers must raise
    appropriate exceptions when this returns False.
    """

    def validate_execution_transition(self, from_status: str, to_status: str) -> bool:
        """Return True if the transition is permitted; False otherwise.

        Rejects any transition FROM a terminal status, and any pair that
        is not in the explicit whitelist above.
        """
        if from_status in _TERMINAL_STATUSES:
            logger.debug(
                "[ExecutionValidationService] Rejected: '%s' is a terminal status.",
                from_status,
            )
            return False

        allowed = (from_status, to_status) in _ALLOWED_TRANSITIONS
        if not allowed:
            logger.debug(
                "[ExecutionValidationService] Rejected: transition '%s' -> '%s' is not permitted.",
                from_status,
                to_status,
            )
        return allowed

    def is_terminal(self, status: str) -> bool:
        """Return True if *status* is a terminal state (no further transitions allowed)."""
        return status in _TERMINAL_STATUSES

    def allowed_next_statuses(self, from_status: str) -> FrozenSet[str]:
        """Return the set of valid next statuses reachable from *from_status*.

        Returns an empty frozenset for terminal statuses or unknown statuses.
        Result ordering is deterministic (frozenset membership is stable for equal sets).
        """
        if from_status in _TERMINAL_STATUSES:
            return frozenset()
        return frozenset(
            to for (frm, to) in _ALLOWED_TRANSITIONS if frm == from_status
        )


# Module-level singleton consumed by container.py and Phase6ExecutionService.
execution_validation_service = ExecutionValidationService()
