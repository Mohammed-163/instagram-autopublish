"""
Bridge: Phase6 (Execution) → Phase7 (Observation).

Subscribes to ExecutionCompleted events published by Phase6's EventBus,
translates them into Phase7's ExecutionCompleted shape, and forwards
them to the Phase7 ApplicationBootstrap.

Phase6 ExecutionCompleted fields:
    execution_id: uuid.UUID
    decision_candidate_id: Optional[str]
    execution_type: str
    result: Dict[str, Any]

Phase7 ExecutionCompleted expected fields:
    execution_id: str
    workflow_id: str
    node_id: str
    tenant_id: str
    payload: Dict[str, Any]
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger("bridges.execution_to_observation")


def _translate_execution_completed(phase6_event: object) -> object:
    """
    Translate a Phase6 ExecutionCompleted into Phase7's ExecutionCompleted.
    """
    # Import Phase7's event type at call time to avoid circular imports
    import phase7_observation  # noqa: F401 — triggers sys.path setup
    from observation.domain.events import ExecutionCompleted as P7ExecutionCompleted

    execution_id = str(getattr(phase6_event, "execution_id", ""))
    execution_type = str(getattr(phase6_event, "execution_type", "unknown"))
    result = dict(getattr(phase6_event, "result", {}))
    decision_candidate_id = str(getattr(phase6_event, "decision_candidate_id", "") or "")

    return P7ExecutionCompleted(
        execution_id=execution_id,
        workflow_id=execution_type,            # best structural mapping
        node_id=decision_candidate_id or execution_type,
        tenant_id="system",                    # system-level tenant for this integration
        payload={"result": result, "execution_type": execution_type},
    )


def wire(phase6_event_bus: object, phase7_bootstrap: object) -> None:
    """
    Wire Phase6's event bus to Phase7's bootstrap.

    Args:
        phase6_event_bus: Phase5/6's core.event_bus.EventBus instance
        phase7_bootstrap: Phase7's observation.application.bootstrap.ApplicationBootstrap
    """
    import phase5_6  # noqa: F401 — triggers sys.path setup
    from core.events import ExecutionCompleted as P6ExecutionCompleted

    def on_execution_completed(event: object) -> None:
        try:
            p7_event = _translate_execution_completed(event)
            phase7_bootstrap.handle_event(p7_event)
        except Exception:
            logger.exception(
                "execution_to_observation bridge failed for event %r", event
            )

    phase6_event_bus.subscribe(P6ExecutionCompleted, on_execution_completed)
    logger.info("execution_to_observation bridge wired: Phase6.ExecutionCompleted → Phase7")
