"""
engines.execution.pipeline — Execution Pipeline (Phase 6 Part 3).

Public surface
--------------
context   : ExecutionContext (canonical immutable context), StageExplainabilityEntry
models    : ExecutionPipelineResult (+ re-exports ExecutionContext, StageExplainabilityEntry)
stage_base: BaseExecutionStage (abstract interface)
stages    : ValidationStage, PreparationStage, ProcessingStage, CleanupStage (skeletons)
registry  : StageRegistry (plugin-style, alphabetically sorted), stage_registry singleton
pipeline  : ExecutionPipeline (sequential stage runner)
factory   : ExecutionPipelineFactory, execution_pipeline_factory singleton

Import convention
-----------------
Prefer importing from the canonical module:
  from engines.execution.pipeline.context import ExecutionContext
  from engines.execution.pipeline.models import ExecutionPipelineResult

Or from this package for convenience:
  from engines.execution.pipeline import ExecutionContext, ExecutionPipelineResult
"""
# Context types — canonical source is context.py
from engines.execution.pipeline.context import (
    ExecutionContext,
    StageExplainabilityEntry,
)

# Pipeline result — defined in models.py
from engines.execution.pipeline.models import ExecutionPipelineResult

# Stage interface
from engines.execution.pipeline.stage_base import BaseExecutionStage

# Concrete skeleton stages
from engines.execution.pipeline.stages import (
    CleanupStage,
    PreparationStage,
    ProcessingStage,
    ValidationStage,
)

# Registry
from engines.execution.pipeline.registry import StageRegistry, stage_registry

# Pipeline runner
from engines.execution.pipeline.pipeline import ExecutionPipeline

# Factory
from engines.execution.pipeline.factory import (
    ExecutionPipelineFactory,
    execution_pipeline_factory,
)

__all__ = [
    # Context
    "ExecutionContext",
    "StageExplainabilityEntry",
    # Result
    "ExecutionPipelineResult",
    # Stage interface
    "BaseExecutionStage",
    # Skeleton stages
    "ValidationStage",
    "PreparationStage",
    "ProcessingStage",
    "CleanupStage",
    # Registry
    "StageRegistry",
    "stage_registry",
    # Pipeline
    "ExecutionPipeline",
    # Factory
    "ExecutionPipelineFactory",
    "execution_pipeline_factory",
]
