"""
YouTubeExecutionAdapter — Phase 6 Part 2 (Platform Adapter Skeleton).

Skeleton implementation of BaseExecutionAdapter for the YouTube platform.

THIS IS A SKELETON ONLY.
  - No YouTube API calls.
  - No OAuth.
  - No video upload.
  - No rendering.
  - No FFmpeg / MoviePy.
  - No media processing of any kind.

All four lifecycle methods return AdapterResult(success=True) as a no-op.
Real implementation will be added in a future phase when actual publishing
capability is built.

Architecture rules enforced here:
  - No repository access.
  - No knowledge of DecisionCandidate — only ExecutionPlan.
  - Data flows only via ExecutionPlan.
"""
from __future__ import annotations

import logging

from engines.execution.adapters.base_adapter import AdapterResult, BaseExecutionAdapter

logger = logging.getLogger(__name__)


class YouTubeExecutionAdapter(BaseExecutionAdapter):
    """Skeleton YouTube adapter — no real operations performed.

    Future phases will implement:
      validate()  → check quota, check credentials, verify content policy
      prepare()   → resolve OAuth token, build upload metadata
      execute()   → upload video via YouTube Data API v3
      cleanup()   → release token, log outcome
    """

    PLATFORM = "youtube"

    # ------------------------------------------------------------------ lifecycle

    def validate(self, plan: "ExecutionPlan") -> AdapterResult:  # noqa: F821
        """Skeleton: validate that the plan targets YouTube.

        No API calls.  No I/O.  Returns success if target_platform matches.
        """
        logger.debug(
            "[YouTubeExecutionAdapter] validate() called for execution_id=%s (skeleton no-op).",
            plan.execution_id,
        )
        if plan.target_platform != self.PLATFORM:
            return AdapterResult(
                success=False,
                step="validate",
                error=(
                    f"YouTubeExecutionAdapter received plan for platform "
                    f"'{plan.target_platform}', expected '{self.PLATFORM}'."
                ),
            )
        return AdapterResult(
            success=True,
            step="validate",
            details={"platform": self.PLATFORM, "execution_id": plan.execution_id},
        )

    def prepare(self, plan: "ExecutionPlan") -> AdapterResult:  # noqa: F821
        """Skeleton: no-op preparation step."""
        logger.debug(
            "[YouTubeExecutionAdapter] prepare() called for execution_id=%s (skeleton no-op).",
            plan.execution_id,
        )
        return AdapterResult(
            success=True,
            step="prepare",
            details={"platform": self.PLATFORM, "execution_id": plan.execution_id},
        )

    def execute(self, plan: "ExecutionPlan") -> AdapterResult:  # noqa: F821
        """Skeleton: no-op execute step.

        IMPORTANT: No YouTube API is called here. No video is uploaded.
        This method is intentionally empty until real execution is built.
        """
        logger.debug(
            "[YouTubeExecutionAdapter] execute() called for execution_id=%s (skeleton no-op).",
            plan.execution_id,
        )
        return AdapterResult(
            success=True,
            step="execute",
            details={"platform": self.PLATFORM, "execution_id": plan.execution_id},
        )

    def cleanup(self, plan: "ExecutionPlan") -> AdapterResult:  # noqa: F821
        """Skeleton: no-op cleanup step."""
        logger.debug(
            "[YouTubeExecutionAdapter] cleanup() called for execution_id=%s (skeleton no-op).",
            plan.execution_id,
        )
        return AdapterResult(
            success=True,
            step="cleanup",
            details={"platform": self.PLATFORM, "execution_id": plan.execution_id},
        )
