"""
ExecutionContext — Phase 6 Part 3 (Execution Pipeline).

Immutable carrier of all state needed by every pipeline stage.
It is the ONLY object passed between stages — stages never communicate
directly with each other.

Architectural rules:
  - Immutable (frozen=True dataclass).
  - No repository access, no DB session, no SQL.
  - No API knowledge — stages only see ExecutionContext.
  - Explainability entries are accumulated per stage via with_stage_entry().
  - Determinism: all ordered collections are tuples, all dicts are built
    with sorted keys.

Explainability invariant: every stage appends a StageExplainabilityEntry
that records stage_name, execution_order, reason, and versions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from engines.execution.execution_plan import ExecutionPlan


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# StageExplainabilityEntry — immutable record added by each stage
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StageExplainabilityEntry:
    """Immutable explainability snapshot written by one pipeline stage.

    Required fields per architecture rule:
      stage_name, execution_order, reason, versions.
    """
    stage_name: str
    execution_order: int
    reason: str
    versions: Dict[str, Any]
    timestamp: datetime = field(default_factory=_utcnow)
    details: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# ExecutionContext
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExecutionContext:
    """Immutable pipeline context.

    Created once by ExecutionPipeline before the first stage runs.
    Each stage produces a *new* context via with_stage_entry() /
    with_metadata() rather than mutating the existing one — preserving
    full immutability and replay determinism.

    Fields:
      execution_plan    : The immutable plan driving this pipeline run.
      adapter           : The resolved BaseExecutionAdapter for this platform.
      current_stage     : Name of the stage currently executing (or '').
      completed_stages  : Tuple of stage names that have finished successfully.
      stage_entries     : Full ordered explainability log (one entry per stage).
      metadata          : Arbitrary key→value bag accumulated across stages.
      versions          : Version tags for this context.
      explainability    : Top-level explainability summary dict.
      started_at        : When the pipeline started (set once, not in fingerprints).
    """
    execution_plan: ExecutionPlan
    adapter: Any                                      # BaseExecutionAdapter (no circular import)

    current_stage: str = ""
    completed_stages: Tuple[str, ...] = field(default_factory=tuple)
    stage_entries: Tuple[StageExplainabilityEntry, ...] = field(default_factory=tuple)

    metadata: Dict[str, Any] = field(default_factory=dict)
    versions: Dict[str, Any] = field(default_factory=dict)
    explainability: Dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=_utcnow)

    # ------------------------------------------------------------------ evolution helpers

    def with_stage_entry(
        self,
        *,
        stage_name: str,
        execution_order: int,
        reason: str,
        versions: Dict[str, Any],
        details: Optional[Dict[str, Any]] = None,
        completed: bool = True,
    ) -> "ExecutionContext":
        """Return a new ExecutionContext with an appended StageExplainabilityEntry.

        If *completed* is True, the stage_name is also added to completed_stages.
        """
        entry = StageExplainabilityEntry(
            stage_name=stage_name,
            execution_order=execution_order,
            reason=reason,
            versions=dict(sorted((versions or {}).items())),  # sort_keys determinism
            details=dict(sorted((details or {}).items())),
        )
        new_entries = self.stage_entries + (entry,)
        new_completed = (
            self.completed_stages + (stage_name,) if completed else self.completed_stages
        )
        return ExecutionContext(
            execution_plan=self.execution_plan,
            adapter=self.adapter,
            current_stage=stage_name,
            completed_stages=new_completed,
            stage_entries=new_entries,
            metadata=self.metadata,
            versions=self.versions,
            explainability=self.explainability,
            started_at=self.started_at,
        )

    def with_metadata(self, updates: Dict[str, Any]) -> "ExecutionContext":
        """Return a new ExecutionContext with *updates* merged into metadata.

        Keys are sorted on merge for determinism.
        """
        merged = dict(sorted({**self.metadata, **updates}.items()))
        return ExecutionContext(
            execution_plan=self.execution_plan,
            adapter=self.adapter,
            current_stage=self.current_stage,
            completed_stages=self.completed_stages,
            stage_entries=self.stage_entries,
            metadata=merged,
            versions=self.versions,
            explainability=self.explainability,
            started_at=self.started_at,
        )

    def with_current_stage(self, stage_name: str) -> "ExecutionContext":
        """Return a new ExecutionContext announcing which stage is about to run."""
        return ExecutionContext(
            execution_plan=self.execution_plan,
            adapter=self.adapter,
            current_stage=stage_name,
            completed_stages=self.completed_stages,
            stage_entries=self.stage_entries,
            metadata=self.metadata,
            versions=self.versions,
            explainability=self.explainability,
            started_at=self.started_at,
        )

    # ------------------------------------------------------------------ introspection

    @property
    def execution_id(self) -> str:
        return self.execution_plan.execution_id

    @property
    def target_platform(self) -> str:
        return self.execution_plan.target_platform

    @property
    def execution_profile(self) -> str:
        return self.execution_plan.execution_profile

    def completed_stage_names(self) -> Tuple[str, ...]:
        """Deterministic tuple of completed stage names (insertion order preserved)."""
        return self.completed_stages

    def total_stages_completed(self) -> int:
        return len(self.completed_stages)

    def __repr__(self) -> str:
        return (
            f"ExecutionContext("
            f"execution_id={self.execution_id!r}, "
            f"current_stage={self.current_stage!r}, "
            f"completed={self.completed_stages})"
        )
