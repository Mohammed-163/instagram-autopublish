"""
StageRegistry — Phase 6 Part 3 (Execution Pipeline).

Plugin-style registry that maps stage names to BaseExecutionStage classes.

Determinism guarantee
---------------------
* The internal dict is re-sorted (alphabetically by stage name) after every
  registration so registered_stages() always returns a stable, predictable
  list regardless of registration order.
* resolve() instantiates a fresh stage object on each call — stages are
  stateless so this is safe and avoids shared-state bugs.

Plugin pattern
--------------
Any module can import stage_registry and call .register(MyStage) to make a
new stage available to pipelines without modifying this file or factory.py.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Type

from engines.execution.pipeline.stage_base import BaseExecutionStage

logger = logging.getLogger(__name__)


class StageRegistry:
    """Maps stage names → BaseExecutionStage classes (plugin-style).

    All internal storage is kept sorted alphabetically so
    ``registered_stages()`` is always deterministic.
    """

    def __init__(self) -> None:
        # Sorted alphabetically at all times.
        self._stages: Dict[str, Type[BaseExecutionStage]] = {}

    # ------------------------------------------------------------------ registration

    def register(self, stage_class: Type[BaseExecutionStage]) -> None:
        """Register *stage_class* under its STAGE_NAME.

        If a stage with the same name is already registered it is replaced
        (last-registration wins — useful for overriding defaults in tests).

        Raises
        ------
        TypeError
            If *stage_class* is not a subclass of BaseExecutionStage.
        ValueError
            If *stage_class*.STAGE_NAME is empty.
        """
        if not (isinstance(stage_class, type) and issubclass(stage_class, BaseExecutionStage)):
            raise TypeError(
                f"stage_class must be a subclass of BaseExecutionStage, "
                f"got {stage_class!r}."
            )
        stage_name: str = stage_class.STAGE_NAME
        if not stage_name:
            raise ValueError(
                f"Cannot register {stage_class.__name__!r}: STAGE_NAME is empty."
            )

        self._stages[stage_name] = stage_class
        # Re-sort after every insert to maintain alphabetical determinism.
        self._stages = dict(sorted(self._stages.items()))

        logger.debug("[StageRegistry] Registered stage '%s' → %s", stage_name, stage_class.__name__)

    # ------------------------------------------------------------------ resolution

    def resolve(self, stage_name: str) -> BaseExecutionStage:
        """Instantiate and return a fresh instance of the named stage.

        Raises
        ------
        KeyError
            If no stage is registered under *stage_name*.
        """
        stage_class = self._stages.get(stage_name)
        if stage_class is None:
            registered = list(self._stages.keys())
            raise KeyError(
                f"No stage registered for '{stage_name}'. "
                f"Registered stages: {registered}."
            )
        return stage_class()

    # ------------------------------------------------------------------ introspection

    def registered_stages(self) -> List[str]:
        """Return the sorted list of all registered stage names."""
        return list(self._stages.keys())

    def is_registered(self, stage_name: str) -> bool:
        """Return True if *stage_name* is present in the registry."""
        return stage_name in self._stages

    def __repr__(self) -> str:
        return f"StageRegistry(stages={self.registered_stages()})"


# ---------------------------------------------------------------------------
# Module-level singleton populated with the four default stages.
# ---------------------------------------------------------------------------

def build_default_stage_registry() -> StageRegistry:
    """Build and return a StageRegistry pre-loaded with all default stages."""
    from engines.execution.pipeline.stages import (
        CleanupStage,
        PreparationStage,
        ProcessingStage,
        ValidationStage,
    )

    registry = StageRegistry()
    # Registration order is irrelevant — the registry sorts alphabetically.
    registry.register(CleanupStage)
    registry.register(PreparationStage)
    registry.register(ProcessingStage)
    registry.register(ValidationStage)

    logger.debug(
        "[StageRegistry] Default registry built with stages: %s",
        registry.registered_stages(),
    )
    return registry


stage_registry: StageRegistry = build_default_stage_registry()
