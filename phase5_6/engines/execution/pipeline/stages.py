"""
Default Pipeline Stages — Phase 6 Part 3 (Execution Pipeline).

Provides the four canonical skeleton stages:
  ValidationStage, PreparationStage, ProcessingStage, CleanupStage.

Architecture rules
------------------
* No real I/O, API calls, file system access, or publishing.
* Each stage appends one StageExplainabilityEntry to the context via
  context.with_stage_entry().  The entry carries:
    stage_name      — this stage's STAGE_NAME
    execution_order — derived dynamically from len(context.completed_stages)+1
                      so it reflects the actual pipeline position, not a
                      hardcoded constant (which would break if stages are
                      reordered or filtered by profile).
    reason          — human-readable description of what this stage did.
    versions        — {"stage_version": "<semver>", "pipeline_phase": "6.3"}
* Explainability is written in cleanup() — the last sub-step — so the entry
  is only recorded once the full stage lifecycle has completed without error.
* All four sub-steps (validate/prepare/process/cleanup) receive and return
  ExecutionContext so the thread-through contract is maintained.
"""
from __future__ import annotations

import logging

from engines.execution.pipeline.models import ExecutionContext
from engines.execution.pipeline.stage_base import BaseExecutionStage

logger = logging.getLogger(__name__)

_STAGE_VERSION = "1.0.0"
_PIPELINE_PHASE = "6.3"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _next_order(context: ExecutionContext) -> int:
    """Derive the next execution_order from the context (deterministic)."""
    return len(context.completed_stages) + 1


# ---------------------------------------------------------------------------
# ValidationStage
# ---------------------------------------------------------------------------

class ValidationStage(BaseExecutionStage):
    """Validates that the execution plan is coherent and actionable.

    Skeleton: no real validation logic — confirms the stage ran.
    """
    STAGE_NAME = "validation"

    def validate(self, context: ExecutionContext) -> ExecutionContext:
        logger.debug("[ValidationStage] validate: plan_id=%s", context.execution_id)
        return context

    def prepare(self, context: ExecutionContext) -> ExecutionContext:
        logger.debug("[ValidationStage] prepare: plan_id=%s", context.execution_id)
        return context

    def process(self, context: ExecutionContext) -> ExecutionContext:
        logger.debug("[ValidationStage] process: plan_id=%s", context.execution_id)
        return context

    def cleanup(self, context: ExecutionContext) -> ExecutionContext:
        order = _next_order(context)
        logger.debug("[ValidationStage] cleanup: recording explainability order=%d", order)
        return context.with_stage_entry(
            stage_name=self.STAGE_NAME,
            execution_order=order,
            reason=(
                "ValidationStage completed: plan structure checked logically. "
                "No API calls or real I/O performed (skeleton phase)."
            ),
            versions=dict(sorted({
                "stage_version": _STAGE_VERSION,
                "pipeline_phase": _PIPELINE_PHASE,
            }.items())),
            details={"platform": context.target_platform},
            completed=True,
        )


# ---------------------------------------------------------------------------
# PreparationStage
# ---------------------------------------------------------------------------

class PreparationStage(BaseExecutionStage):
    """Prepares prerequisites required before execution begins.

    Skeleton: no real preparation — confirms the stage ran.
    """
    STAGE_NAME = "preparation"

    def validate(self, context: ExecutionContext) -> ExecutionContext:
        logger.debug("[PreparationStage] validate: plan_id=%s", context.execution_id)
        return context

    def prepare(self, context: ExecutionContext) -> ExecutionContext:
        logger.debug("[PreparationStage] prepare: plan_id=%s", context.execution_id)
        return context

    def process(self, context: ExecutionContext) -> ExecutionContext:
        logger.debug("[PreparationStage] process: plan_id=%s", context.execution_id)
        return context

    def cleanup(self, context: ExecutionContext) -> ExecutionContext:
        order = _next_order(context)
        logger.debug("[PreparationStage] cleanup: recording explainability order=%d", order)
        return context.with_stage_entry(
            stage_name=self.STAGE_NAME,
            execution_order=order,
            reason=(
                "PreparationStage completed: prerequisites confirmed logically. "
                "No credentials, rate-limit checks, or real I/O performed (skeleton phase)."
            ),
            versions=dict(sorted({
                "stage_version": _STAGE_VERSION,
                "pipeline_phase": _PIPELINE_PHASE,
            }.items())),
            details={"execution_profile": context.execution_profile},
            completed=True,
        )


# ---------------------------------------------------------------------------
# ProcessingStage
# ---------------------------------------------------------------------------

class ProcessingStage(BaseExecutionStage):
    """Performs the core platform execution logic.

    Skeleton: no real processing — confirms the stage ran.
    """
    STAGE_NAME = "processing"

    def validate(self, context: ExecutionContext) -> ExecutionContext:
        logger.debug("[ProcessingStage] validate: plan_id=%s", context.execution_id)
        return context

    def prepare(self, context: ExecutionContext) -> ExecutionContext:
        logger.debug("[ProcessingStage] prepare: plan_id=%s", context.execution_id)
        return context

    def process(self, context: ExecutionContext) -> ExecutionContext:
        logger.debug("[ProcessingStage] process: plan_id=%s", context.execution_id)
        return context

    def cleanup(self, context: ExecutionContext) -> ExecutionContext:
        order = _next_order(context)
        logger.debug("[ProcessingStage] cleanup: recording explainability order=%d", order)
        return context.with_stage_entry(
            stage_name=self.STAGE_NAME,
            execution_order=order,
            reason=(
                "ProcessingStage completed: core execution logic ran logically. "
                "No platform API calls, uploads, or rendering performed (skeleton phase)."
            ),
            versions=dict(sorted({
                "stage_version": _STAGE_VERSION,
                "pipeline_phase": _PIPELINE_PHASE,
            }.items())),
            details={
                "platform": context.target_platform,
                "execution_profile": context.execution_profile,
            },
            completed=True,
        )


# ---------------------------------------------------------------------------
# CleanupStage
# ---------------------------------------------------------------------------

class CleanupStage(BaseExecutionStage):
    """Releases resources and finalises the pipeline run.

    Skeleton: no real cleanup — confirms the stage ran.
    """
    STAGE_NAME = "cleanup"

    def validate(self, context: ExecutionContext) -> ExecutionContext:
        logger.debug("[CleanupStage] validate: plan_id=%s", context.execution_id)
        return context

    def prepare(self, context: ExecutionContext) -> ExecutionContext:
        logger.debug("[CleanupStage] prepare: plan_id=%s", context.execution_id)
        return context

    def process(self, context: ExecutionContext) -> ExecutionContext:
        logger.debug("[CleanupStage] process: plan_id=%s", context.execution_id)
        return context

    def cleanup(self, context: ExecutionContext) -> ExecutionContext:
        order = _next_order(context)
        logger.debug("[CleanupStage] cleanup: recording explainability order=%d", order)
        return context.with_stage_entry(
            stage_name=self.STAGE_NAME,
            execution_order=order,
            reason=(
                "CleanupStage completed: resource teardown confirmed logically. "
                "No real resources to release in skeleton phase."
            ),
            versions=dict(sorted({
                "stage_version": _STAGE_VERSION,
                "pipeline_phase": _PIPELINE_PHASE,
            }.items())),
            details={"completed_before_cleanup": list(context.completed_stages)},
            completed=True,
        )
