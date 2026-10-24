"""Collect cumulative Instagram insights at six post-age milestones.

The snapshot table is created idempotently. A milestone is committed only
after its learning observations are persisted, so transient failures retry.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import requests
from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib import config
from lib.error_handler import handle_unexpected
from lib.gemini_client import GeminiClient
from lib.instagram_client import InstagramClient, InstagramAPIError
from lib.sheets_client import SheetsClient
from lib.telegram_notifier import TelegramNotifier

MILESTONES = (("1h", 1), ("2h", 2), ("6h", 6), ("24h", 24), ("3d", 72), ("7d", 168))
INSIGHTS_METRICS = ("reach", "saved", "likes", "comments", "shares", "views", "total_interactions")
SUPPORTED_MEDIA_PRODUCT_TYPES = {"FEED", "REELS", "CAROUSEL_ALBUM"}


def _parse_datetime(value: object) -> datetime | None:
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def ensure_snapshot_table(engine) -> None:
    """Create our append-only snapshot ledger without modifying existing tables."""
    ddl = """
    CREATE TABLE IF NOT EXISTS instagram_insight_snapshots (
        media_id TEXT NOT NULL,
        snapshot_period TEXT NOT NULL,
        target_at TIMESTAMP WITH TIME ZONE NOT NULL,
        published_at TIMESTAMP WITH TIME ZONE NOT NULL,
        captured_at TIMESTAMP WITH TIME ZONE NOT NULL,
        topic_slug TEXT,
        hook_line TEXT,
        ayah_key TEXT,
        ayah_text TEXT,
        iraqi_explanation TEXT,
        visual_style TEXT,
        music_file TEXT,
        reach BIGINT, saved BIGINT, shares BIGINT, likes BIGINT, comments BIGINT,
        views BIGINT, total_interactions BIGINT,
        PRIMARY KEY (media_id, snapshot_period),
        CHECK (snapshot_period IN ('1h','2h','6h','24h','3d','7d'))
    )
    """
    with engine.begin() as connection:
        connection.execute(text(ddl))
        for name in ("reach", "saved", "shares", "likes", "comments", "views", "total_interactions"):
            connection.execute(text(
                f"ALTER TABLE instagram_insight_snapshots ADD COLUMN IF NOT EXISTS {name} BIGINT"
            ))


def _read_snapshots(engine, media_id: str) -> dict[str, dict]:
    with engine.begin() as connection:
        rows = connection.execute(text(
            "SELECT snapshot_period FROM instagram_insight_snapshots WHERE media_id=:media_id"
        ), {"media_id": media_id}).all()
    return {period: True for (period,) in rows}


def _save_snapshot(engine, row: dict, period: str, target_at: datetime,
                   captured_at: datetime, metrics: dict) -> None:
    values = {
        "media_id": str(row["media_id"]), "snapshot_period": period,
        "target_at": target_at, "published_at": _parse_datetime(row["published_at"]),
        "captured_at": captured_at, "topic_slug": row.get("topic_slug"),
        "hook_line": row.get("hook_line"), "ayah_key": row.get("ayah_key"),
        "ayah_text": row.get("ayah_text"), "iraqi_explanation": row.get("iraqi_explanation"),
        "visual_style": row.get("visual_style"), "music_file": row.get("music_file"),
    }
    for name in ("reach", "saved", "shares", "likes", "comments", "views", "total_interactions"):
        value = metrics.get(name)
        values[name] = int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO instagram_insight_snapshots
            (media_id,snapshot_period,target_at,published_at,captured_at,topic_slug,hook_line,
             ayah_key,ayah_text,iraqi_explanation,visual_style,music_file,
             reach,saved,shares,likes,comments,views,total_interactions)
            VALUES (:media_id,:snapshot_period,:target_at,:published_at,:captured_at,:topic_slug,
                    :hook_line,:ayah_key,:ayah_text,:iraqi_explanation,:visual_style,:music_file,
                    :reach,:saved,:shares,:likes,:comments,:views,:total_interactions)
            ON CONFLICT (media_id,snapshot_period) DO NOTHING
        """), values)


def _persist_learning(factory, row: dict, period: str, metrics: dict,
                      captured_at: datetime) -> None:
    """Persist period-specific signals: the weekly planner can compare like with like."""
    from phase8_learning.database.models import LearningObservationModel

    LearningObservationModel.__table__.create(factory.engine, checkfirst=True)
    session = factory.new_session()
    context = {
        "media_id": str(row["media_id"]), "snapshot_period": period,
        "captured_at": captured_at.isoformat(), "topic_slug": row.get("topic_slug", ""),
        "hook_line": row.get("hook_line", ""), "ayah_key": row.get("ayah_key", ""),
        "ayah_text": row.get("ayah_text", ""),
        "iraqi_explanation": row.get("iraqi_explanation", ""),
        "visual_style": row.get("visual_style", ""), "music_file": row.get("music_file", ""),
    }
    try:
        for name, value in metrics.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            metric_name = f"{name}_{period}"
            existing = session.query(LearningObservationModel).filter_by(
                media_id=context["media_id"], metric_name=metric_name
            ).order_by(LearningObservationModel.created_at.desc()).first()
            if existing:
                existing.metric_value = float(value)
                existing.context = context
            else:
                session.add(LearningObservationModel(
                    observation_id=f"{context['media_id']}:{period}:{name}",
                    media_id=context["media_id"], subject_id=(row.get("topic_slug") or context["media_id"])[:255],
                    metric_name=metric_name, metric_value=float(value), context=context,
                ))
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def fetch_media_insights(ig, media_id):
    metadata = ig._request("GET", str(media_id), params={"fields": "media_product_type,media_type"})
    product_type = str(metadata.get("media_product_type") or "UNKNOWN").upper()
    media_type = str(metadata.get("media_type") or "").upper()
    if media_type in {"IMAGE", "VIDEO"} and product_type not in SUPPORTED_MEDIA_PRODUCT_TYPES:
        return None, product_type
    if product_type not in SUPPORTED_MEDIA_PRODUCT_TYPES and media_type != "CAROUSEL_ALBUM":
        raise InstagramAPIError(f"unsupported media type: {product_type}/{media_type or 'UNKNOWN'}")

    try:
        data = ig._request("GET", f"{media_id}/insights", params={"metric": ",".join(INSIGHTS_METRICS)})
        items = data.get("data", [])
    except InstagramAPIError:
        # Metric availability can vary by media type/API version. Keep every
        # metric that is individually supported instead of losing the snapshot.
        items = []
        for metric in INSIGHTS_METRICS:
            try:
                items.extend(ig._request("GET", f"{media_id}/insights", params={"metric": metric}).get("data", []))
            except InstagramAPIError:
                continue
    result = {}
    for item in items:
        values = item.get("values", [])
        if values:
            result[item["name"]] = values[0].get("value")
    return result, product_type


def _initialize_learning():
    from phase8_learning.config.settings import Settings
    from phase8_learning.database.connection import DatabaseConnectionFactory
    factory = DatabaseConnectionFactory(Settings.from_env())
    ensure_snapshot_table(factory.engine)
    return factory


def main():
    config.check_required_env_vars(["GOOGLE_SHEET_ID", "IG_ACCESS_TOKEN", "IG_BUSINESS_ID",
                                    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"])
    notifier = TelegramNotifier(config.require_env("TELEGRAM_BOT_TOKEN"), config.require_env("TELEGRAM_CHAT_ID"))
    sheets = SheetsClient(config.load_sheets_service_account_json(), config.require_env("GOOGLE_SHEET_ID"))
    if sheets.is_paused():
        print("System is paused. Exiting.")
        return

    ig = InstagramClient(config.require_env("IG_ACCESS_TOKEN"), config.require_env("IG_BUSINESS_ID"))
    factory = _initialize_learning()
    gemini_keys = [config.optional_env(f"GEMINI_API_KEY_{i}") for i in (1, 2, 3)]
    gemini = GeminiClient(gemini_keys) if any(gemini_keys) else None
    now = datetime.now(timezone.utc)
    daily_rows = sheets._ws(config.DAILY_LOG_TAB).get_all_records()  # noqa: SLF001
    live_media = ig._request("GET", f"{ig.ig_business_id}/media", params={
        "fields": "id,caption,timestamp,media_type,media_product_type", "limit": 100,
    }).get("data", [])
    media_by_id = {str(item.get("id")): item for item in live_media}
    fetched = 0

    try:
        for row_index, original in enumerate(daily_rows, start=2):
            if original.get("status") not in (config.STATUS_PUBLISHED, config.STATUS_CLEANED):
                continue
            if not original.get("media_id") or not original.get("published_at"):
                continue
            published_at = _parse_datetime(original["published_at"])
            if published_at is None:
                continue
            media = media_by_id.get(str(original["media_id"]))
            if not media:
                topic = str(original.get("topic_slug") or "").casefold()
                hook = str(original.get("hook_line") or "").casefold()
                candidates = [item for item in live_media
                              if (topic and topic in str(item.get("caption") or "").casefold())
                              or (hook and hook in str(item.get("caption") or "").casefold())]
                if len(candidates) == 1:
                    media = candidates[0]
            if not media:
                continue
            row = {**original, "media_id": str(media["id"])}
            existing = _read_snapshots(factory.engine, row["media_id"])
            due = [(period, hours, published_at + timedelta(hours=hours))
                   for period, hours in MILESTONES
                   if now >= published_at + timedelta(hours=hours) and period not in existing]
            if not due:
                continue
            # One milestone per post per workflow run: if GitHub delays a run,
            # do not pretend one current cumulative count was six historical readings.
            due = due[:1]
            metrics, media_type = fetch_media_insights(ig, row["media_id"])
            if metrics is None:
                print(f"Skipping unsupported carousel child {row['media_id']} ({media_type})")
                continue
            if not metrics:
                raise RuntimeError(f"Instagram returned no usable insight metrics for {row['media_id']}; milestone left pending for retry.")
            for period, hours, target_at in due:
                captured_at = datetime.now(timezone.utc)
                try:
                    _persist_learning(factory, row, period, metrics, captured_at)
                    _save_snapshot(factory.engine, row, period, target_at, captured_at, metrics)
                    # Keep the human-readable tab useful without making it the source of truth.
                    sheets.append_post_performance({
                        "date": row.get("date", ""), "topic_slug": row.get("topic_slug", ""),
                        "hook_line": row.get("hook_line", ""), "fact_line": row.get("fact_line", ""),
                        "caption_arabic": row.get("caption_arabic", ""), "hashtags": row.get("hashtags", ""),
                        "media_id": row["media_id"], "published_at": row.get("published_at", ""),
                        "fetched_at": captured_at.isoformat(), "snapshot_period": period,
                        "target_at": target_at.isoformat(),
                        "reach": metrics.get("reach", ""), "saved": metrics.get("saved", ""),
                        "shares": metrics.get("shares", ""), "likes": metrics.get("likes", ""),
                        "comments": metrics.get("comments", ""), "views": metrics.get("views", ""),
                        "ayah_key": row.get("ayah_key", ""), "ayah_text": row.get("ayah_text", ""),
                        "iraqi_explanation": row.get("iraqi_explanation", ""),
                        "music_file": row.get("music_file", ""), "visual_style": row.get("visual_style", ""),
                    })
                    fetched += 1
                    print(f"Saved {period} cumulative insights for {row['media_id']} at {captured_at.isoformat()}")
                except Exception as exc:
                    print(f"Retry next run: {row.get('topic_slug', row['media_id'])}/{period}: {exc}")
                    raise
    except (InstagramAPIError, requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
        print(f"Transient Instagram/API error; due measurements will be retried: {exc}")
    except Exception:
        if gemini:
            handle_unexpected(notifier, gemini, config.optional_env("GH_PAT"),
                              config.optional_env("GH_REPO"), "scripts/fetch_insights.py",
                              "scheduled cumulative insight collection", now.date().isoformat())
        raise
    finally:
        factory.engine.dispose()
    print(f"Saved {fetched} milestone snapshot(s); schedule: 1h, 2h, 6h, 24h, 3d, 7d.")


if __name__ == "__main__":
    main()
