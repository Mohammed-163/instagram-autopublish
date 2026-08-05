"""
models.py — Phase 6 Part 3 (Execution Pipeline).

Thin re-export shim.  ExecutionContext and StageExplainabilityEntry live in
context.py (the canonical, fully-immutable implementation).  This module
re-exports them alongside ExecutionPipelineResult so every other module in
this package can import from a single ``pipeline.models`` namespace.

Why a shim instead of merging?
  context.py owns the immutable-context evolution helpers (with_stage_entry,
  with_metadata, with_current_stage) and carries its own docstring explaining
  the invariants.  Keeping it separate makes the architectural intent clear
  and avoids a god-module.  All consumers that already import from
  ``pipeline.models`` continue to work unchanged after this shim is added.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

# Re-export the canonical immutable context types from context.py.
# stage_base, stages, pipeline, orchestrator, and __init__ all import
# ExecutionContext from here — they all therefore get the full implementation
# that includes with_current_stage(), with_metadata(), and with_stage_entry().
from engines.execution.pipeline.context import (  # noqa: F401  (re-export)
    ExecutionContext,
    StageExplainabilityEntry,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# ExecutionPipelineResult — immutable result of a complete pipeline run
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExecutionPipelineResult:
    """Immutable result returned by ExecutionPipeline.run().

    Fields
    ------
    success          : True if every stage completed without raising.
    completed_stages : Ordered tuple of stage names that finished successfully.
    failed_stage     : Stage name that caused the first failure, or None.
    execution_time   : Wall-clock seconds from pipeline start to end.
    explainability   : Accumulated explainability dict from the final context
                       (includes the 'stage_entries' list written by stages).
    """
    success: bool
    completed_stages: Tuple[str, ...]
    failed_stage: Optional[str]
    execution_time: float
    explainability: Dict[str, Any] = field(default_factory=dict)
