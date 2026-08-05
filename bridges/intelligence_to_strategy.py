"""
Bridge: Phase10 (Intelligence Core) → Phase5/6 (Strategy/Decision - feedback loop).

Subscribes to Phase10's published events (RuleEvolved, StrategyEvolved,
ConfidenceCalibrated) and routes them back into Phase5/6's event bus
to close the learning feedback loop.

This bridge completes the autonomous AI cycle:

  Phase10 Intelligence Core
       |  RuleEvolved / StrategyEvolved / ConfidenceCalibrated
       v
  Phase5/6 Strategy Planning & Decision (feedback)
       |  → triggers new planning/decision cycles
       v
  ... (loop continues)
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("bridges.intelligence_to_strategy")


def wire(
    phase10_publisher: object,
    phase56_event_bus: object,
) -> None:
    """
    Wire Phase10's publisher to Phase5/6's event bus for the feedback loop.

    Phase10 uses string-based event_type dispatch; this bridge subscribes
    to the wildcard "*" to catch all Phase10 events and forward the
    relevant ones to Phase5/6.

    Args:
        phase10_publisher: Phase10's InMemoryEventPublisher instance
        phase56_event_bus: Phase5/6's core.event_bus.EventBus instance
    """
    import phase5_6  # noqa: F401 — ensures Phase5/6 sys.path is set up
    from core.events import KnowledgeUpdated as P56KnowledgeUpdated

    def on_phase10_event(event: object) -> None:
        event_type = getattr(event, "event_type", "")
        subject_key = getattr(event, "subject_key", "")
        payload = dict(getattr(event, "payload", {}))

        try:
            if event_type in (
                "rule.evolved",
                "strategy.evolved",
                "confidence.calibrated",
                "planning.cycle_completed",
            ):
                # Translate into a KnowledgeUpdated event that Phase5/6 understands
                feedback_event = P56KnowledgeUpdated(
                    knowledge_version_id=None,
                    summary=f"Phase10 feedback: {event_type} — key={subject_key}",
                )
                phase56_event_bus.publish(feedback_event)
                logger.debug(
                    "intelligence_to_strategy: forwarded %s as KnowledgeUpdated", event_type
                )
        except Exception:
            logger.exception(
                "intelligence_to_strategy bridge failed for event_type=%s", event_type
            )

    phase10_publisher.subscribe("*", on_phase10_event)
    logger.info(
        "intelligence_to_strategy bridge wired: Phase10 events → Phase5/6.KnowledgeUpdated"
    )
