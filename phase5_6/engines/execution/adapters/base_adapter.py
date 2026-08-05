"""
BaseExecutionAdapter — Phase 6 Part 2 (Platform Adapter Interface).

Abstract interface that every platform-specific adapter must implement.
This is the ONLY contract between ExecutionOrchestrator and any platform.

Architectural rules enforced here:
  - No repository access.
  - No DB session, no SQL.
  - No knowledge of DecisionCandidate — only ExecutionPlan.
  - No API calls in this base class.
  - No real execution logic.

The four lifecycle methods map directly to the four standard steps
in every ExecutionPlan:
  validate()  → confirm the plan is actionable for this platform
  prepare()   → set up any preconditions (no I/O in skeleton)
  execute()   → perform the platform operation (skeleton only)
  cleanup()   → release any resources (skeleton only)

All methods receive an ExecutionPlan and return an AdapterResult
so the Orchestrator can track step outcomes without coupling to
platform internals.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AdapterResult — value object returned by every adapter method
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AdapterResult:
    """Immutable result of a single adapter lifecycle step.

    success  : True if the step completed without error.
    step     : which lifecycle method produced this result.
    details  : arbitrary metadata (platform-specific, kept generic here).
    error    : human-readable error message if success=False.
    """
    success: bool
    step: str                                   # "validate" | "prepare" | "execute" | "cleanup"
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.success and self.error is None:
            # Enforce: failed results must carry an error message
            object.__setattr__(self, "error", "Unspecified adapter error.")


# ---------------------------------------------------------------------------
# BaseExecutionAdapter — abstract interface
# ---------------------------------------------------------------------------

class BaseExecutionAdapter(ABC):
    """Abstract base for all platform execution adapters.

    Subclasses (YouTubeExecutionAdapter, InstagramExecutionAdapter, …)
    implement the four lifecycle methods for their target platform.

    Contract:
      - Receives only ExecutionPlan — never a DecisionCandidate.
      - Never accesses a repository directly.
      - Never makes real API calls in the base class.
      - Returns AdapterResult from every method.
    """

    #: Platform identifier that must match AdapterRegistry keys, e.g. "youtube"
    PLATFORM: str = ""

    # ------------------------------------------------------------------ interface

    @abstractmethod
    def validate(self, plan: "ExecutionPlan") -> AdapterResult:  # noqa: F821
        """Verify that the ExecutionPlan is actionable for this platform.

        No I/O.  No API calls.  Pure logic only.
        Returns AdapterResult(success=True) if the plan is valid.
        """

    @abstractmethod
    def prepare(self, plan: "ExecutionPlan") -> AdapterResult:  # noqa: F821
        """Set up any preconditions required before execution.

        In skeletons this is a no-op.  Concrete implementations will
        resolve credentials, check rate limits, etc. — but only when
        real execution is built in a future phase.
        """

    @abstractmethod
    def execute(self, plan: "ExecutionPlan") -> AdapterResult:  # noqa: F821
        """Perform the platform-specific operation.

        In skeletons this is a no-op.  Real implementation lives in a
        future phase.  Must NOT be called with real credentials here.
        """

    @abstractmethod
    def cleanup(self, plan: "ExecutionPlan") -> AdapterResult:  # noqa: F821
        """Release any resources acquired during prepare() / execute().

        In skeletons this is a no-op.
        """

    # ------------------------------------------------------------------ helpers

    def platform_name(self) -> str:
        """Return the canonical platform identifier for this adapter."""
        return self.PLATFORM

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(platform={self.PLATFORM!r})"
