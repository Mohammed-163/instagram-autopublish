"""
ExecutionPipeline — Phase 6 Part 3 (Execution Pipeline).

Runs a fixed sequence of named pipeline stages against an ExecutionContext,
collecting explainability from each stage and returning a deterministic
ExecutionPipelineResult.

Architecture rules
------------------
* Stages are resolved from StageRegistry by name — no hardcoded imports.
* Execution is sequential and halts on the first stage failure.
* The context is threaded immutably through the stage sequence: each stage
  receives the context returned by the previous stage.
* with_current_stage() is called before each stage so the context always
  reflects which stage is active.
* Explainability in the result is assembled from two sources:
    - context.explainability (top-level summary dict set at pipeline start)
    - context.stage_entries  (tuple of StageExplainabilityEntry, one per stage)
  They are merged into a single dict under the key "stage_entries" so
  callers see a unified explainability payload.
* No retry, no worker, no queue, no real I/O.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Tuple

from engines.execution.pipeline.models import ExecutionContext, ExecutionPipelineResult
from engines.execution.pipeline.registry import StageRegistry

logger = logging.getLogger(__name__)


def _build_explainability(context: ExecutionContext) -> Dict[str, Any]:
    """Merge context.explainability with the stage_entries tuple into one dict.

    The result is sorted by key for determinism (sort_keys=True semantics).
    """
    stage_entries_serialised = [
        {
            "stage_name": e.stage_name,
            "execution_order": e.execution_order,
            "reason": e.reason,
            "versions": dict(sorted(e.versions.items())),
            "details": dict(sorted(e.details.items())),
            "timestamp": e.timestamp.isoformat(),
        }
        for e in context.stage_entries
    ]
    merged: Dict[str, Any] = dict(sorted({
        **context.explainability,
        "stage_entries": stage_entries_serialised,
        "completed_stages": list(context.completed_stages),
    }.items()))
    return merged


class ExecutionPipeline:
    """Executes a defined sequence of pipeline stages sequentially.

    Parameters
    ----------
    stages:
        Ordered tuple of stage names to execute (e.g. ("validation",
        "preparation", "processing", "cleanup")).  Names must be
        registered in *stage_registry*.
    stage_registry:
        StageRegistry that resolves stage names → BaseExecutionStage
        instances.

    Usage
    -----
        result = pipeline.run(context)
    """

    PIPELINE_VERSION = "1.0.0"

    def __init__(
        self,
        stages: Tuple[str, ...],
        stage_registry: StageRegistry,
    ) -> None:
        if not stages:
            raise ValueError("ExecutionPipeline requires at least one stage name.")
        if not isinstance(stage_registry, StageRegistry):
            raise TypeError(
                f"ExecutionPipeline requires a StageRegistry, "
                f"got {type(stage_registry).__name__!r}."
            )
        self._stages: Tuple[str, ...] = stages
        self._registry: StageRegistry = stage_registry

    # ------------------------------------------------------------------ public API

    def run(self, context: ExecutionContext) -> ExecutionPipelineResult:
        """Run all configured stages sequentially.

        Each stage is resolved from the registry, receives the current
        context, and returns an evolved context.  If any stage raises,
        execution halts and the failed stage name is recorded.

        Returns
        -------
        ExecutionPipelineResult
            success=True only if every configured stage completed without error.
            explainability contains both the top-level summary and the ordered
            list of per-stage entries produced by each stage's cleanup().
        """
        logger.info(
            "[ExecutionPipeline] Starting pipeline for execution_id=%s stages=%s",
            context.execution_id,
            self._stages,
        )

        start_time = time.monotonic()
        current_ctx = context
        failed_stage: str | None = None

        for stage_name in self._stages:
            # Announce which stage is about to run (immutable context evolution).
            current_ctx = current_ctx.with_current_stage(stage_name)

            logger.debug(
                "[ExecutionPipeline] Running stage '%s' for execution_id=%s",
                stage_name,
                context.execution_id,
            )

            try:
                stage = self._registry.resolve(stage_name)
                current_ctx = stage.run(current_ctx)
            except Exception as exc:
                logger.exception(
                    "[ExecutionPipeline] Stage '%s' raised %s: %s",
                    stage_name,
                    type(exc).__name__,
                    exc,
                )
                failed_stage = stage_name
                break

        execution_time = time.monotonic() - start_time
        success = failed_stage is None

        logger.info(
            "[ExecutionPipeline] Finished execution_id=%s success=%s "
            "completed=%s failed=%r elapsed=%.4fs",
            context.execution_id,
            success,
            current_ctx.completed_stages,
            failed_stage,
            execution_time,
        )

        return ExecutionPipelineResult(
            success=success,
            completed_stages=current_ctx.completed_stages,
            failed_stage=failed_stage,
            execution_time=round(execution_time, 6),
            explainability=_build_explainability(current_ctx),
        )
