"""
Bridge: Phase7 (Observation) → Phase8 (Learning).
"""
from __future__ import annotations
import logging
from typing import Callable, Iterable

logger = logging.getLogger("bridges.observation_to_learning")


def _translate(phase7_event: object) -> object:
    from phase8_learning.events.events import ObservationRecorded as P8ObservationRecorded
    return P8ObservationRecorded(
        observation_id=str(getattr(phase7_event, "observation_id", "")),
        subject_id=str(getattr(phase7_event, "tenant_id", "system")),
        metric_name="observation_recorded",
        metric_value=1.0,
        context={
            "fingerprint": str(getattr(phase7_event, "fingerprint", "")),
            "tenant_id": str(getattr(phase7_event, "tenant_id", "system")),
        },
    )


def wire(phase7_in_process_publisher: object,
         phase8_run: Callable[[Iterable[object]], list]) -> None:
    from observation.domain.events import ObservationRecorded as P7ObservationRecorded

    def on_observation_recorded(event: object) -> None:
        if not isinstance(event, P7ObservationRecorded):
            return
        try:
            phase8_run([_translate(event)])
        except Exception:
            logger.exception("observation_to_learning bridge failed for %r", event)

    phase7_in_process_publisher.subscribe(P7ObservationRecorded, on_observation_recorded)
    logger.info("observation_to_learning bridge wired: Phase7.ObservationRecorded → Phase8")
