"""
Phase6ExecutionEngine — Phase 6 Part 1, 2, & 3 (Execution Layer).

Responsibilities:
  - Subscribe to DecisionCandidateApproved.
  - Delegate to Phase6ExecutionService.create_execution() to create an
    ExecutionRecord (status=Pending) and publish ExecutionPending.
  - Drive the full execution lifecycle through Phase6ExecutionService:
      Pending → Scheduled → Running → Completed / Failed
  - Use ExecutionPlanFactory to build an ExecutionPlan from the record.
  - Delegate orchestration to ExecutionOrchestrator (which runs the
    ExecutionPipeline internally).
  - Map OrchestrationResult → Phase6ExecutionService lifecycle transitions.

This engine performs NO real execution:
  - No publishing to Instagram / YouTube / any external API.
  - No file uploads, rendering, or media processing.
  - No scheduling, queuing, or worker dispatch.
  - No repository access (Engine → Service → Repository rule enforced).

Architecture invariant:
  Engine → Service only.
  Service → Repository only.
  Repository → Database only.
  ALL lifecycle updates go ONLY through Phase6ExecutionService.
  EventBus events are published ONLY by Phase6ExecutionService transitions.

All configurable parameters come from SettingsService.
No business values are embedded in this file.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from core.events import DecisionCandidateApproved
from engines.shared.engine_base import EngineBase

logger = logging.getLogger(__name__)


class Phase6ExecutionEngine(EngineBase):
    """Converts DecisionCandidateApproved → full execution lifecycle.

    Flow per approved decision:
      1. create_execution()  → ExecutionRecord(Pending)  + ExecutionPending event
      2. schedule()          → ExecutionRecord(Scheduled) + ExecutionScheduled event
      3. start()             → ExecutionRecord(Running)   + ExecutionStarted event
      4. Build ExecutionPlan via ExecutionPlanFactory.build_from_execution_record()
      5. Run ExecutionOrchestrator.run(plan)
      6a. If success: complete() → ExecutionRecord(Completed) + ExecutionCompleted event
      6b. If failure: fail()     → ExecutionRecord(Failed)    + ExecutionFailed event

    All lifecycle updates go ONLY through Phase6ExecutionService.
    EventBus events are published ONLY inside Phase6ExecutionService._transition().
    """

    ENGINE_NAME = "phase6_execution"

    def __init__(
        self,
        event_bus: Any,
        phase6_execution_service: Any,
        execution_orchestrator: Any = None,
        execution_plan_factory: Any = None,
        health_service: Any = None,
        settings_service: Any = None,
    ) -> None:
        super().__init__(health_service=health_service, settings_service=settings_service)
        self.event_bus = event_bus
        self.phase6_execution_service = phase6_execution_service
        self._execution_orchestrator = execution_orchestrator
        self._execution_plan_factory = execution_plan_factory

    # ------------------------------------------------------------------ lazy resolvers

    @property
    def _orchestrator(self) -> Any:
        if self._execution_orchestrator is not None:
            return self._execution_orchestrator
        from engines.execution.orchestrator import execution_orchestrator
        return execution_orchestrator

    @property
    def _plan_factory(self) -> Any:
        if self._execution_plan_factory is not None:
            return self._execution_plan_factory
        from engines.execution.factory import execution_plan_factory
        return execution_plan_factory

    # ------------------------------------------------------------------ handler

    def handle_decision_candidate_approved(self, event: DecisionCandidateApproved) -> None:
        """React to an approved decision by running the full execution lifecycle.

        Architecture:
          ALL lifecycle transitions are performed ONLY via Phase6ExecutionService.
          The EventBus receives events ONLY from within Phase6ExecutionService.

        No execution is performed. No APIs are called. No media is processed.
        """
        decision_candidate_id = str(event.decision_candidate_id)
        try:
            logger.info(
                "[Phase6ExecutionEngine] DecisionCandidateApproved received "
                "for candidate %s — starting execution lifecycle.",
                decision_candidate_id,
            )

            settings = self._load_settings()
            target_platform = settings.get("default_target_platform", "instagram")
            actor = getattr(event, "actor", "system")

            # ----------------------------------------------------------------
            # Step 1: Create ExecutionRecord (Pending) + publish ExecutionPending
            # ----------------------------------------------------------------
            record = self.phase6_execution_service.create_execution(
                decision_candidate_id=decision_candidate_id,
                execution_type=settings.get(
                    "default_execution_type", "execute_strategy_candidate"
                ),
                objective_profile=settings.get("objective_profile", ""),
                versions={"engine_version": self.ENGINE_NAME},
                explainability=dict(sorted({
                    "source_event": DecisionCandidateApproved.EVENT_TYPE,
                    "decision_candidate_id": decision_candidate_id,
                    "actor": actor,
                    "reason": getattr(event, "reason", ""),
                }.items())),
            )

            execution_id = record.id

            logger.info(
                "[Phase6ExecutionEngine] ExecutionRecord created (Pending) "
                "execution_id=%s for decision_candidate_id=%s.",
                execution_id,
                decision_candidate_id,
            )

            # ----------------------------------------------------------------
            # Step 2: Pending → Scheduled (Phase6ExecutionService publishes ExecutionScheduled)
            # ----------------------------------------------------------------
            self.phase6_execution_service.schedule(
                execution_id,
                reason="Execution scheduled by Phase6ExecutionEngine.",
                actor=actor,
            )

            # ----------------------------------------------------------------
            # Step 3: Scheduled → Running (Phase6ExecutionService publishes ExecutionStarted)
            # ----------------------------------------------------------------
            self.phase6_execution_service.start(
                execution_id,
                reason="Execution started by Phase6ExecutionEngine.",
                actor=actor,
            )

            # ----------------------------------------------------------------
            # Step 4: Build ExecutionPlan from the persisted record.
            # No repository access — record was returned by create_execution().
            # ----------------------------------------------------------------
            plan = self._plan_factory.build_from_execution_record(
                execution_record=record,
                target_platform=target_platform,
                settings=settings,
            )

            logger.info(
                "[Phase6ExecutionEngine] ExecutionPlan built plan_id=%s "
                "for execution_id=%s platform=%s profile=%s.",
                plan.plan_id,
                execution_id,
                plan.target_platform,
                plan.execution_profile,
            )

            # ----------------------------------------------------------------
            # Step 5: Run the orchestrator → pipeline → adapters (skeletons only).
            # No real I/O. No API calls. No publishing.
            # ----------------------------------------------------------------
            orchestration_result = self._orchestrator.run(plan)

            logger.info(
                "[Phase6ExecutionEngine] Orchestration finished execution_id=%s "
                "success=%s failed_step=%r.",
                execution_id,
                orchestration_result.success,
                orchestration_result.failed_step,
            )

            # ----------------------------------------------------------------
            # Step 6: Lifecycle terminal transition via Phase6ExecutionService only.
            # EventBus events are published ONLY inside _transition().
            # ----------------------------------------------------------------
            if orchestration_result.success:
                self.phase6_execution_service.complete(
                    execution_id,
                    result=dict(sorted({
                        "plan_id": plan.plan_id,
                        "completed_steps": list(orchestration_result.completed_steps),
                        "pipeline_explainability": orchestration_result.pipeline_explainability,
                        "summary": orchestration_result.summary,
                    }.items())),
                    reason="All pipeline stages completed successfully.",
                    actor=actor,
                )
                logger.info(
                    "[Phase6ExecutionEngine] Execution completed (Completed) "
                    "execution_id=%s.",
                    execution_id,
                )
            else:
                failure_reason = (
                    f"Pipeline stage failed: {orchestration_result.failed_step!r}. "
                    f"Summary: {orchestration_result.summary}"
                )
                self.phase6_execution_service.fail(
                    execution_id,
                    failure_reason=failure_reason,
                    reason=failure_reason,
                    actor=actor,
                )
                logger.warning(
                    "[Phase6ExecutionEngine] Execution failed (Failed) "
                    "execution_id=%s failed_step=%r.",
                    execution_id,
                    orchestration_result.failed_step,
                )

            self.heartbeat("healthy")

        except Exception as exc:
            logger.exception(
                "[Phase6ExecutionEngine] Unhandled error during execution lifecycle "
                "for decision_candidate_id=%s: %s",
                decision_candidate_id,
                exc,
            )
            self.heartbeat("error", error=str(exc))
            # Best-effort: attempt to mark the record as Failed if we know its id.
            self._try_fail_on_error(
                exc=exc,
                decision_candidate_id=decision_candidate_id,
                actor="system",
            )

    # ------------------------------------------------------------------ helpers

    def _load_settings(self) -> dict:
        """Load execution-layer settings from SettingsService (key: 'execution_layer').

        All numeric thresholds and business values come from here.
        Returns an empty dict if settings are unavailable so the engine
        degrades gracefully.
        """
        try:
            return self._settings_service.get("execution_layer", {}) or {}
        except Exception:
            return {}

    def _try_fail_on_error(
        self,
        *,
        exc: Exception,
        decision_candidate_id: str,
        actor: str,
    ) -> None:
        """Best-effort attempt to mark a Running execution as Failed on unexpected error.

        Silently swallows any secondary exception so the original error is not masked.
        """
        try:
            records = self.phase6_execution_service.get_by_decision_candidate(
                decision_candidate_id
            )
            for record in (records or []):
                if record.status == "Running":
                    self.phase6_execution_service.fail(
                        record.id,
                        failure_reason=f"Unhandled engine error: {exc}",
                        reason=f"Unhandled engine error: {exc}",
                        actor=actor,
                    )
                    logger.warning(
                        "[Phase6ExecutionEngine] Marked execution_id=%s as Failed "
                        "after unhandled error.",
                        record.id,
                    )
        except Exception as secondary:
            logger.debug(
                "[Phase6ExecutionEngine] Could not mark execution as Failed "
                "after error: %s",
                secondary,
            )
