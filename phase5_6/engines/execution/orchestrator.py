"""
ExecutionOrchestrator — Phase 6 Part 2 & Part 3 (Execution Orchestrator).

Single responsibility: receive an ExecutionPlan and walk it through the
ExecutionPipeline — tracking which stages are pending, current, completed,
and remaining — without performing any real execution.

THIS IS LOGIC ONLY.
  - No API calls.
  - No file uploads.
  - No rendering.
  - No publishing.
  - No repository access (Engine → Service → Repository rule enforced).
  - No knowledge of DecisionCandidate — only ExecutionPlan.

The orchestrator:
  1. Resolves the correct platform adapter via AdapterRegistry.
  2. Builds an ExecutionContext for the pipeline.
  3. Delegates execution to ExecutionPipeline (resolved via
     execution_pipeline_factory).
  4. Assembles an OrchestrationResult for Phase6ExecutionService to
     drive lifecycle transitions.

Architecture rules enforced here:
  Engine → Service only.
  Orchestrator → Adapter only (via AdapterRegistry).
  Orchestrator does NOT access Repository.
  Orchestrator does NOT call Phase6ExecutionService directly —
    the caller (Phase6ExecutionEngine or a wiring module) does.
  Data flows via ExecutionPlan only.

All lifecycle updates (Pending→Scheduled→Running→Completed/Failed) are
performed exclusively by Phase6ExecutionService — never from here.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from engines.execution.adapters.base_adapter import AdapterResult
from engines.execution.adapters.registry import AdapterRegistry
from engines.execution.execution_plan import ExecutionPlan, ExecutionStep
from engines.execution.pipeline.models import ExecutionContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# StepOutcome — immutable result of one orchestrated step
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StepOutcome:
    """Immutable result of a single orchestration step."""
    step_name: str
    step_order: int
    success: bool
    adapter_result: AdapterResult
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# OrchestrationResult — immutable final result of a full plan run
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OrchestrationResult:
    """Immutable result of running a complete ExecutionPlan through the orchestrator.

    success           : True if ALL pipeline stages completed without error.
    plan_id           : Links back to the ExecutionPlan.plan_id.
    execution_id      : Links back to ExecutionRecord.id.
    completed_steps   : Steps that finished successfully (in order).
    failed_step       : The step that caused failure, or None.
    remaining_steps   : Steps that were NOT reached (because of a failure).
    step_outcomes     : Full ordered log of every step attempted.
    pipeline_explainability : Explainability dict from the pipeline result.
    summary           : Human-readable outcome description.
    details           : Arbitrary extra metadata.
    """
    success: bool
    plan_id: str
    execution_id: str

    completed_steps: Tuple[str, ...]     # step_names, deterministic order
    failed_step: Optional[str]           # step_name or None
    remaining_steps: Tuple[str, ...]     # step_names not yet reached

    step_outcomes: Tuple[StepOutcome, ...]   # full ordered log

    pipeline_explainability: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# ExecutionOrchestrator
# ---------------------------------------------------------------------------

class ExecutionOrchestrator:
    """Walks an ExecutionPlan through the pipeline using the appropriate platform adapter.

    The orchestrator is stateless — it holds no mutable state between calls.
    Every call to run() is independent and produces an immutable OrchestrationResult.

    Architectural rules:
      - Receives AdapterRegistry (injected, not created here).
      - No repository access.
      - No direct API calls.
      - Data flows via ExecutionPlan only.
      - Lifecycle transitions are performed exclusively by Phase6ExecutionService
        (the caller, not this class).
    """

    ORCHESTRATOR_NAME = "execution_orchestrator"

    def __init__(self, adapter_registry: AdapterRegistry) -> None:
        if not isinstance(adapter_registry, AdapterRegistry):
            raise TypeError(
                f"ExecutionOrchestrator requires an AdapterRegistry, "
                f"got {type(adapter_registry).__name__!r}."
            )
        self._registry = adapter_registry

    # ------------------------------------------------------------------ public API

    def run(self, plan: ExecutionPlan) -> OrchestrationResult:
        """Execute all pipeline stages for *plan* and return an OrchestrationResult.

        Steps:
          1. Resolve the platform adapter (fail fast if unknown).
          2. Build an ExecutionContext carrying the plan + adapter.
          3. Run the ExecutionPipeline (profile → stage sequence).
          4. Map pipeline stage outcomes to StepOutcome records.
          5. Return an OrchestrationResult — caller drives lifecycle transitions.

        No real I/O, API calls, or publishing happen here — adapters are
        skeletons in this phase.
        """
        logger.info(
            "[ExecutionOrchestrator] Starting orchestration for plan_id=%s"
            " execution_id=%s platform=%s steps=%d",
            plan.plan_id,
            plan.execution_id,
            plan.target_platform,
            plan.total_steps,
        )

        # Resolve adapter once — fail fast if platform is unknown
        try:
            adapter = self._registry.resolve(plan.target_platform)
        except KeyError as exc:
            logger.error(
                "[ExecutionOrchestrator] No adapter for platform '%s': %s",
                plan.target_platform,
                exc,
            )
            return self._build_result(
                plan=plan,
                completed=[],
                failed_step=None,
                remaining=list(plan.step_names),
                outcomes=[],
                success=False,
                summary=str(exc),
                pipeline_explainability={},
            )

        # Import lazily to avoid circular-import at module load time.
        from engines.execution.pipeline.factory import execution_pipeline_factory

        context = ExecutionContext(
            execution_plan=plan,
            adapter=adapter,
            versions=dict(sorted({
                "orchestrator": self.ORCHESTRATOR_NAME,
                "factory_version": plan.versions.get("factory_version", ""),
            }.items())),
            explainability=dict(sorted({
                "plan_id": plan.plan_id,
                "platform": plan.target_platform,
                "execution_profile": plan.execution_profile,
            }.items())),
        )

        pipeline = execution_pipeline_factory.build_pipeline(plan.execution_profile)
        pipeline_result = pipeline.run(context)

        completed = list(pipeline_result.completed_stages)
        failed_step = pipeline_result.failed_stage

        outcomes: List[StepOutcome] = []
        for idx, stage in enumerate(completed, start=1):
            outcomes.append(StepOutcome(
                step_name=stage,
                step_order=idx,
                success=True,
                adapter_result=AdapterResult(success=True, step=stage),
            ))

        if failed_step:
            outcomes.append(StepOutcome(
                step_name=failed_step,
                step_order=len(completed) + 1,
                success=False,
                adapter_result=AdapterResult(
                    success=False,
                    step=failed_step,
                    error="Pipeline stage failed.",
                ),
                error="Pipeline stage failed.",
            ))

        remaining = [
            s for s in plan.step_names
            if s not in completed and s != failed_step
        ]

        summary = (
            f"Orchestration {'succeeded' if pipeline_result.success else 'failed'} "
            f"for plan_id={plan.plan_id}. "
            f"Completed: {completed}. "
            f"Failed: {failed_step!r}. "
            f"Remaining: {remaining}."
        )

        logger.info("[ExecutionOrchestrator] %s", summary)

        return self._build_result(
            plan=plan,
            completed=completed,
            failed_step=failed_step,
            remaining=remaining,
            outcomes=outcomes,
            success=pipeline_result.success,
            summary=summary,
            pipeline_explainability=dict(sorted(pipeline_result.explainability.items())),
        )

    # ------------------------------------------------------------------ step tracking helpers

    def next_step(self, plan: ExecutionPlan, completed_step_names: List[str]) -> Optional[ExecutionStep]:
        """Return the next ExecutionStep not yet in *completed_step_names*, or None.

        Deterministic: iterates ordered_steps (already sorted by order, step_name).
        """
        completed_set = set(completed_step_names)
        for step in plan.ordered_steps:
            if step.step_name not in completed_set:
                return step
        return None

    def remaining_steps(
        self, plan: ExecutionPlan, completed_step_names: List[str]
    ) -> Tuple[ExecutionStep, ...]:
        """Return all steps not yet in *completed_step_names*, in deterministic order."""
        completed_set = set(completed_step_names)
        return tuple(s for s in plan.ordered_steps if s.step_name not in completed_set)

    def current_step(
        self, plan: ExecutionPlan, completed_step_names: List[str]
    ) -> Optional[ExecutionStep]:
        """Alias for next_step() — the step currently being (or about to be) executed."""
        return self.next_step(plan, completed_step_names)

    # ------------------------------------------------------------------ internal

    def _dispatch_step(
        self,
        adapter: Any,
        step: ExecutionStep,
        plan: ExecutionPlan,
    ) -> AdapterResult:
        """Route a step to the correct adapter lifecycle method.

        Maps step_name → adapter method.  Unknown step names return a
        success result to remain forward-compatible (new steps added in
        later phases won't break the current orchestrator).
        """
        dispatch: Dict[str, Any] = {
            "validate": adapter.validate,
            "prepare":  adapter.prepare,
            "execute":  adapter.execute,
            "cleanup":  adapter.cleanup,
        }
        method = dispatch.get(step.step_name)
        if method is None:
            logger.debug(
                "[ExecutionOrchestrator] Unknown step_name '%s' — treating as no-op success.",
                step.step_name,
            )
            return AdapterResult(
                success=True,
                step=step.step_name,
                details={"note": "Unknown step type — no-op forward-compat."},
            )
        return method(plan)

    @staticmethod
    def _build_result(
        *,
        plan: ExecutionPlan,
        completed: List[str],
        failed_step: Optional[str],
        remaining: List[str],
        outcomes: List[StepOutcome],
        success: bool,
        summary: str,
        pipeline_explainability: Dict[str, Any],
    ) -> OrchestrationResult:
        return OrchestrationResult(
            success=success,
            plan_id=plan.plan_id,
            execution_id=plan.execution_id,
            completed_steps=tuple(completed),
            failed_step=failed_step,
            remaining_steps=tuple(remaining),
            step_outcomes=tuple(outcomes),
            pipeline_explainability=dict(sorted(pipeline_explainability.items())),
            summary=summary,
            details=dict(sorted({
                "platform": plan.target_platform,
                "execution_profile": plan.execution_profile,
                "total_steps": plan.total_steps,
            }.items())),
        )


# ---------------------------------------------------------------------------
# Module-level singleton consumed by container.py
# ---------------------------------------------------------------------------

def build_default_orchestrator() -> ExecutionOrchestrator:
    from engines.execution.adapters.registry import adapter_registry
    return ExecutionOrchestrator(adapter_registry=adapter_registry)


execution_orchestrator = build_default_orchestrator()
