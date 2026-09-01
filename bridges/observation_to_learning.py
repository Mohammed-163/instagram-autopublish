"""
Bridge: Phase7 (Observation) → Phase8 (Learning).
"""
from __future__ import annotations

import logging
from numbers import Number
from typing import Any, Callable, Iterable, List
from uuid import UUID

logger = logging.getLogger("bridges.observation_to_learning")


def _fallback_event(phase7_event: object, event_type: Any) -> object:
    return event_type(
        observation_id=str(getattr(phase7_event, "observation_id", "")),
        subject_id=str(getattr(phase7_event, "tenant_id", "system")),
        metric_name="observation_recorded",
        metric_value=1.0,
        context={
            "fingerprint": str(getattr(phase7_event, "fingerprint", "")),
            "tenant_id": str(getattr(phase7_event, "tenant_id", "system")),
        },
    )


def _translate(phase7_event: object) -> List[object]:
    from phase8_learning.events.events import (
        ObservationRecorded as P8ObservationRecorded,
    )

    observation_id = str(getattr(phase7_event, "observation_id", ""))
    tenant_id = str(getattr(phase7_event, "tenant_id", "system"))
    fingerprint = str(getattr(phase7_event, "fingerprint", ""))

    observation = None
    session = None
    db_factory = None

    try:
        from observation.config import load_settings
        from observation.infrastructure.db.connection import (
            DatabaseConnectionFactory,
        )
        from observation.infrastructure.repository.observation_repository import (
            SQLAlchemyObservationRepository,
        )

        db_factory = DatabaseConnectionFactory(load_settings().database)
        session = db_factory.new_session()

        repository = SQLAlchemyObservationRepository(session)
        observation = repository.find_by_id(UUID(observation_id))

    except Exception:
        logger.warning(
            "observation_to_learning: could not load Observation %s; "
            "using fallback",
            observation_id,
            exc_info=True,
        )

    finally:
        if session is not None:
            session.close()

        if db_factory is not None:
            db_factory.dispose()

    if observation is None:
        return [_fallback_event(phase7_event, P8ObservationRecorded)]

    payload = getattr(observation, "payload", {})
    result = payload.get("result", {}) if isinstance(payload, dict) else {}

    if not isinstance(result, dict):
        result = {}

    metric_names = (
        "reach",
        "saved",
        "likes",
        "comments",
        "shares",
    )

    content_keys = (
        "topic_slug",
        "hook_line",
    )

    context = {
        "fingerprint": fingerprint,
        "tenant_id": tenant_id,
    }

    for key in content_keys:
        if result.get(key) is not None:
            context[key] = str(result[key])

    translated = []

    for metric_name in metric_names:
        value = result.get(metric_name)

        if isinstance(value, bool) or not isinstance(value, Number):
            continue

        translated.append(
            P8ObservationRecorded(
                observation_id=observation_id,
                subject_id=tenant_id,
                metric_name=metric_name,
                metric_value=float(value),
                context=dict(context),
            )
        )

    if not translated:
        translated.append(
            _fallback_event(
                phase7_event,
                P8ObservationRecorded,
            )
        )

    return translated


def wire(
    phase7_in_process_publisher: object,
    phase8_run: Callable[[Iterable[object]], list],
) -> None:
    from observation.domain.events import (
        ObservationRecorded as P7ObservationRecorded,
    )

    def on_observation_recorded(event: object) -> None:
        if not isinstance(event, P7ObservationRecorded):
            return

        try:
            phase8_run(_translate(event))
        except Exception:
            logger.exception(
                "observation_to_learning bridge failed for %r",
                event,
            )

    phase7_in_process_publisher.subscribe(
        P7ObservationRecorded,
        on_observation_recorded,
    )

    logger.info(
        "observation_to_learning bridge wired: "
        "Phase7.ObservationRecorded → Phase8"
    )
