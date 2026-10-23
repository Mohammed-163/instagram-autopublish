"""
BaseExecutionStage — Phase 6 Part 3 (Execution Pipeline).

Abstract interface every pipeline stage must implement.

Spec mandates exactly four abstract methods: validate(), prepare(),
process(), cleanup().  No additional abstract members are required;
STAGE_NAME is a plain class attribute (str) that subclasses must set —
accessing it on the class (for registration) must return the string
directly, which rules out @property here.

The concrete run() method is a template-method that calls the four steps
in order.  Stages must NOT mutate the received context — every step
returns a (potentially new) ExecutionContext.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

# Import the canonical immutable context from models (which re-exports
# the full implementation from context.py including with_current_stage etc.)
from engines.execution.pipeline.models import ExecutionContext

logger = logging.getLogger(__name__)


class BaseExecutionStage(ABC):
    """Abstract base for all pipeline stages.

    Subclasses must:
      1. Define a non-empty class attribute  STAGE_NAME: str  (e.g. "validation").
         It must be a class-level attribute — NOT a property — because
         StageRegistry reads it via ``stage_class.STAGE_NAME`` before any
         instance is created.
      2. Implement the four abstract lifecycle methods below.

    No real side-effects are allowed in skeleton stages.  Every method
    receives an ExecutionContext and returns an (optionally evolved) one.
    """

    # Subclasses set this at class level, e.g.:  STAGE_NAME = "validation"
    STAGE_NAME: str = ""

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Validate that concrete subclasses set a non-empty STAGE_NAME."""
        super().__init_subclass__(**kwargs)
        # Only enforce on concrete (non-abstract) subclasses.
        if not getattr(cls, "__abstractmethods__", None):
            if not cls.STAGE_NAME:
                raise TypeError(
                    f"{cls.__name__} must define a non-empty class attribute STAGE_NAME."
                )

    # ------------------------------------------------------------------ interface

    @abstractmethod
    def validate(self, context: ExecutionContext) -> ExecutionContext:
        """Validate that this stage can run against *context*."""

    @abstractmethod
    def prepare(self, context: ExecutionContext) -> ExecutionContext:
        """Prepare any prerequisites this stage needs."""

    @abstractmethod
    def process(self, context: ExecutionContext) -> ExecutionContext:
        """Execute the core logic of this stage (skeleton: no real I/O)."""

    @abstractmethod
    def cleanup(self, context: ExecutionContext) -> ExecutionContext:
        """Clean up after processing and append the explainability entry."""

    # ------------------------------------------------------------------ template method

    def run(self, context: ExecutionContext) -> ExecutionContext:
        """Template method: run the full stage lifecycle in order.

        Each concrete lifecycle method receives the context returned by the
        previous one — context is threaded through without mutation.
        """
        ctx = self.validate(context)
        ctx = self.prepare(ctx)
        ctx = self.process(ctx)
        ctx = self.cleanup(ctx)
        return ctx
