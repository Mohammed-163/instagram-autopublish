"""
ExecutionPipelineFactory — Phase 6 Part 3 (Execution Pipeline).

Creates ExecutionPipeline instances from an ExecutionProfile string.

Architecture rules
------------------
* No hardcoded business logic about which platform gets which stages.
* Profile → stage-name-tuple mapping is a pure structural decision with
  no knowledge of YouTube, Instagram, OAuth, FFmpeg, or any other real
  execution concern.
* The factory delegates stage resolution entirely to StageRegistry
  (plugin-style); it only decides *which names* to sequence.
* All stage sequences are deterministically ordered tuples.
* Unknown profiles fall back to the default four-stage sequence rather
  than raising, so new profiles added in later phases never break existing
  orchestration.
"""
from __future__ import annotations

import logging
from typing import Dict, Tuple

from engines.execution.pipeline.pipeline import ExecutionPipeline
from engines.execution.pipeline.registry import StageRegistry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Profile → ordered stage tuple mapping.
# No business logic — just names.  Add new profiles here as phases expand.
# All tuples are sorted only when the caller needs an alphabetical view;
# pipeline execution order is preserved exactly as declared.
# ---------------------------------------------------------------------------

_DEFAULT_STAGES: Tuple[str, ...] = (
    "validation",
    "preparation",
    "processing",
    "cleanup",
)

# Profile overrides: these map named execution profiles to custom stage sequences.
# All stage names must be registered in StageRegistry at call time.
# Order within each tuple is execution order (not alphabetical).
_PROFILE_STAGE_MAP: Dict[str, Tuple[str, ...]] = {
    "express": (
        "validation",
        "processing",
        "cleanup",
    ),
    "engagement": (
        "validation",
        "preparation",
        "processing",
        "cleanup",
    ),
    "growth": (
        "validation",
        "preparation",
        "processing",
        "cleanup",
    ),
    "retention": (
        "validation",
        "preparation",
        "processing",
        "cleanup",
    ),
}


class ExecutionPipelineFactory:
    """Creates ExecutionPipeline instances from an execution profile name.

    The factory holds no mutable state — every build_pipeline() call
    produces a fresh ExecutionPipeline wrapping the shared stage_registry.

    Parameters
    ----------
    stage_registry:
        The StageRegistry that the created pipelines will use to resolve
        stage names at run time.
    """

    FACTORY_VERSION = "1.0.0"

    def __init__(self, stage_registry: StageRegistry) -> None:
        if not isinstance(stage_registry, StageRegistry):
            raise TypeError(
                f"ExecutionPipelineFactory requires a StageRegistry, "
                f"got {type(stage_registry).__name__!r}."
            )
        self._registry = stage_registry

    # ------------------------------------------------------------------ public API

    def build_pipeline(self, execution_profile: str) -> ExecutionPipeline:
        """Return an ExecutionPipeline configured for *execution_profile*.

        If *execution_profile* is unknown, the default four-stage sequence
        is used so new profiles added in later phases never break.

        Parameters
        ----------
        execution_profile:
            Value from ExecutionPlan.execution_profile (e.g. "growth",
            "engagement", "express").

        Returns
        -------
        ExecutionPipeline
            Fresh pipeline instance ready to call .run(context).
        """
        stages: Tuple[str, ...] = _PROFILE_STAGE_MAP.get(
            execution_profile, _DEFAULT_STAGES
        )

        logger.info(
            "[ExecutionPipelineFactory] Building pipeline for profile=%r stages=%s "
            "factory_version=%s",
            execution_profile,
            stages,
            self.FACTORY_VERSION,
        )

        return ExecutionPipeline(stages=stages, stage_registry=self._registry)

    # ------------------------------------------------------------------ introspection

    def available_profiles(self) -> Tuple[str, ...]:
        """Return the sorted tuple of profiles with explicit stage overrides.

        The default profile is always available but is not listed here
        since it applies to every unknown profile.
        """
        return tuple(sorted(_PROFILE_STAGE_MAP.keys()))


# ---------------------------------------------------------------------------
# Module-level singleton consumed by ExecutionOrchestrator and container.py
# ---------------------------------------------------------------------------

def build_default_pipeline_factory() -> ExecutionPipelineFactory:
    """Build and return the default ExecutionPipelineFactory."""
    from engines.execution.pipeline.registry import stage_registry
    return ExecutionPipelineFactory(stage_registry=stage_registry)


execution_pipeline_factory: ExecutionPipelineFactory = build_default_pipeline_factory()
