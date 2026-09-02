"""
Bridge: Phase7 (Observation) → Phase8 (Learning).
"""
from __future__ import annotations

import logging
import os
from numbers import Number
from typing import Any, Callable, Iterable, List

logger = logging.getLogger("bridges.observation_to_learning")
_sheets_client = None
_daily_log_by_media_id = None


def _fetch_daily_log_row(media_id: str) -> dict:
    global _sheets_client, _daily_log_by_media_id
    from phase5_6.lib import config
    from phase5_6.lib.sheets_client import SheetsClient
    if _sheets_client is None:
        _sheets_client = SheetsClient(config.load_sheets_service_account_json(), config.require_env("GOOGLE_SHEET_ID"))
    if _daily_log_by_media_id is None:
        rows = _sheets_client._ws(config.DAILY_LOG_TAB).get_all_records()  # noqa: SLF001
        _daily_log_by_media_id = {
            str(row.get("media_id")): row
            for row in rows
            if row.get("media_id")
        }
    row = _daily_log_by_media_id.get(str(media_id))
    if row is not None:
        return row
    raise LookupError(f"no Daily_Log row found for media_id={media_id}")


def _fallback_event(phase7_event: object, event_type: Any, subject_id: str) -> object:
    return event_type(
        observation_id=str(getattr(phase7_event, "observation_id", "")),
        subject_id=subject_id,
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

    payload = getattr(phase7_event, "payload", {})
    result = payload.get("result", {}) if isinstance(payload, dict) else {}

    if not isinstance(result, dict):
        result = {}

    media_id = str(result.get("media_id") or getattr(phase7_event, "media_id", "") or "")
    plan_row = {}
    try:
        if not media_id:
            raise LookupError("event does not contain media_id")
        plan_row = _fetch_daily_log_row(media_id)
    except Exception as exc:
        logger.warning("Could not read Daily_Log for media_id=%s: %s", media_id or "unknown", exc)

    topic_slug = str(plan_row.get("topic_slug") or "").strip()
    hook_type = str(plan_row.get("hook_type") or "").strip()
    subject_id = (topic_slug or hook_type or f"media_{media_id or observation_id}").strip()[:255]

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
                subject_id=subject_id,
                metric_name=metric_name,
                metric_value=float(value),
                context=dict(context),
            )
        )

    if translated:
        try:
            from phase8_learning.config.settings import Settings
            from phase8_learning.database.connection import DatabaseConnectionFactory
            from phase8_learning.repository.learning_observation_repository import save_metrics
            settings = Settings.from_env()
            db_url = settings.database_url
            masked = db_url.split("@")[-1] if "@" in db_url else db_url[:15] + "..."
            logger.warning("[DEBUG] learning_observations will write to host: %s", masked)
            for var in [
                "LEARNING_LAYER_DATABASE_URL",
                "KCL_DATABASE_URL",
                "P10_DATABASE_URL",
                "DATABASE_URL",
            ]:
                logger.warning("[DEBUG] %s is set: %s", var, bool(os.environ.get(var)))
            logger.warning("[DEBUG] translated metrics count: %d", len(translated))
            factory = DatabaseConnectionFactory(settings)
            session = factory.new_session()
            try:
                save_metrics(
                    session, observation_id, subject_id,
                    [(item.metric_name, item.metric_value) for item in translated],
                    dict(context),
                )
            finally:
                session.close()
                factory.engine.dispose()
        except Exception:
            logger.exception("Could not persist learning observations for observation_id=%s", observation_id)

    if not translated:
        translated.append(
            _fallback_event(
                phase7_event,
                P8ObservationRecorded,
                subject_id,
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
