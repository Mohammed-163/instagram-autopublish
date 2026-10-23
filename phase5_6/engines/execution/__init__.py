"""
engines.execution — Phase 6 (Execution Orchestrator & Pipeline).

Package contents:
  execution_plan  : ExecutionPlan, ExecutionStep, RetryPolicy (immutable domain models)
  factory         : ExecutionPlanFactory — builds ExecutionPlan from approved decision data
                    or from an existing ExecutionRecord
  orchestrator    : ExecutionOrchestrator, OrchestrationResult, StepOutcome
  adapters/       : BaseExecutionAdapter, platform skeletons, AdapterRegistry
  pipeline/       : ExecutionPipeline, ExecutionPipelineFactory, StageRegistry,
                    BaseExecutionStage, concrete stages, ExecutionContext,
                    ExecutionPipelineResult
"""
from engines.execution.execution_plan import ExecutionPlan, ExecutionStep, RetryPolicy
from engines.execution.factory import ExecutionPlanFactory, execution_plan_factory
from engines.execution.orchestrator import (
    ExecutionOrchestrator,
    OrchestrationResult,
    StepOutcome,
    execution_orchestrator,
)

__all__ = [
    # Domain models
    "ExecutionPlan",
    "ExecutionStep",
    "RetryPolicy",
    # Factory
    "ExecutionPlanFactory",
    "execution_plan_factory",
    # Orchestrator
    "ExecutionOrchestrator",
    "OrchestrationResult",
    "StepOutcome",
    "execution_orchestrator",
]
