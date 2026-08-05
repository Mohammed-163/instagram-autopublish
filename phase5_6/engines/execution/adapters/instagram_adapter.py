"""
InstagramExecutionAdapter — Phase 6 Part 2 (Platform Adapter Skeleton).

Skeleton implementation of BaseExecutionAdapter for the Instagram platform.

THIS IS A SKELETON ONLY.
  - No Instagram Graph API calls.
  - No OAuth.
  - No media upload.
  - No image/video processing.
  - No FFmpeg / MoviePy.
  - No media of any kind.

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


class InstagramExecutionAdapter(BaseExecutionAdapter):
    """Skeleton Instagram adapter — no real operations performed.

    Future phases will implement:
      validate()  → check content policy, verify media specs (aspect ratio, duration)
      prepare()   → resolve Graph API token, build container request
      execute()   → publish via Instagram Graph API (container create → publish)
      cleanup()   → release token, log media_id, record publish timestamp
    """

    PLATFORM = "instagram"

    # ------------------------------------------------------------------ lifecycle

    def validate(self, plan: "ExecutionPlan") -> AdapterResult:  # noqa: F821
        """Skeleton: validate that the plan targets Instagram.

        No API calls.  No I/O.  Returns success if target_platform matches.
        """
        logger.debug(
            "[InstagramExecutionAdapter] validate() called for execution_id=%s (skeleton no-op).",
            plan.execution_id,
        )
        if plan.target_platform != self.PLATFORM:
            return AdapterResult(
                success=False,
                step="validate",
                error=(
                    f"InstagramExecutionAdapter received plan for platform "
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
            "[InstagramExecutionAdapter] prepare() called for execution_id=%s (skeleton no-op).",
            plan.execution_id,
        )
        return AdapterResult(
            success=True,
            step="prepare",
            details={"platform": self.PLATFORM, "execution_id": plan.execution_id},
        )

    def execute(self, plan: "ExecutionPlan") -> AdapterResult:  # noqa: F821
        """Skeleton: no-op execute step.

        IMPORTANT: No Instagram Graph API is called here. No media is uploaded.
        This method is intentionally empty until real execution is built.
        """
        logger.debug(
            "[InstagramExecutionAdapter] execute() called for execution_id=%s (skeleton no-op).",
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
            "[InstagramExecutionAdapter] cleanup() called for execution_id=%s (skeleton no-op).",
            plan.execution_id,
        )
        return AdapterResult(
            success=True,
            step="cleanup",
            details={"platform": self.PLATFORM, "execution_id": plan.execution_id},
        )
