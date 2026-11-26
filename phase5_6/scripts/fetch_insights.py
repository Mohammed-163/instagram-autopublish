"""Collect cumulative Instagram insights at six post-age milestones.

The snapshot table is created idempotently. A milestone is committed only
after its learning observations are persisted, so transient failures retry.
"""
from __future__ import annotations

import os
import json
import math
import sys
from datetime import datetime, timedelta, timezone

from requests import RequestException
from sqlalchemy import inspect, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib import config
from lib.instagram_client import InstagramClient, InstagramAPIError
from lib.sheets_client import SheetsClient

MILESTONES = (("1h", 1), ("2h", 2), ("6h", 6), ("24h", 24), ("3d", 72), ("7d", 168))
MAX_SNAPSHOT_DELAY = timedelta(minutes=30)
INSIGHTS_METRICS = ("reach", "saved", "likes", "comments", "shares", "views", "total_interactions")
# Keep IG Media Insights names and native numeric units in metrics_json:
# average watch time is milliseconds; skip rate is Meta's first-three-second rate
# as returned (do not assume/convert a fraction or a percentage).
REELS_RETENTION_METRICS = ("ig_reels_avg_watch_time", "reels_skip_rate")
RETENTION_TIMEOUT_SECONDS = 4
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
        scheduled_time TIMESTAMP WITH TIME ZONE,
        captured_at TIMESTAMP WITH TIME ZONE NOT NULL,
        topic_slug TEXT,
        hook_line TEXT,
        ayah_key TEXT,
        ayah_text TEXT,
        iraqi_explanation TEXT,
        background_query TEXT,
        visual_style TEXT,
        music_file TEXT,
        metrics_json TEXT,
        reach BIGINT, saved BIGINT, shares BIGINT, likes BIGINT, comments BIGINT,
        views BIGINT, total_interactions BIGINT,
        PRIMARY KEY (media_id, snapshot_period),
        CHECK (snapshot_period IN ('1h','2h','6h','24h','3d','7d'))
    )
    """
    with engine.begin() as connection:
        connection.execute(text(ddl))
    columns = {column["name"] for column in inspect(engine).get_columns("instagram_insight_snapshots")}
    additions = {
        "scheduled_time": "TIMESTAMP WITH TIME ZONE", "background_query": "TEXT",
        "metrics_json": "TEXT", "reach": "BIGINT", "saved": "BIGINT",
        "shares": "BIGINT", "likes": "BIGINT", "comments": "BIGINT",
        "views": "BIGINT", "total_interactions": "BIGINT",
    }
    for name, sql_type in additions.items():
        if name not in columns:
            with engine.begin() as connection:
                connection.execute(text(
                    f"ALTER TABLE instagram_insight_snapshots ADD COLUMN {name} {sql_type}"
                ))


def _read_snapshots(engine, media_id: str) -> set[str]:
    with engine.begin() as connection:
        rows = connection.execute(text(
            "SELECT snapshot_period FROM instagram_insight_snapshots WHERE media_id=:media_id"
        ), {"media_id": media_id}).all()
    return {period for (period,) in rows}


def _save_snapshot(session, row: dict, period: str, target_at: datetime,
                   captured_at: datetime, metrics: dict) -> bool:
    values = {
        "media_id": str(row["media_id"]), "snapshot_period": period,
        "target_at": target_at, "published_at": _parse_datetime(row["published_at"]),
        "scheduled_time": _parse_datetime(row.get("scheduled_time")),
        "captured_at": captured_at, "topic_slug": row.get("topic_slug"),
        "hook_line": row.get("hook_line"), "ayah_key": row.get("ayah_key"),
        "ayah_text": row.get("ayah_text"), "iraqi_explanation": row.get("iraqi_explanation"),
        "background_query": row.get("background_query"),
        "visual_style": row.get("visual_style"), "music_file": row.get("music_file"),
        "metrics_json": json.dumps(metrics, ensure_ascii=False),
    }
    for name in ("reach", "saved", "shares", "likes", "comments", "views", "total_interactions"):
        value = metrics.get(name)
        values[name] = int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
    result = session.execute(text("""
            INSERT INTO instagram_insight_snapshots
            (media_id,snapshot_period,target_at,published_at,scheduled_time,captured_at,topic_slug,hook_line,
             ayah_key,ayah_text,iraqi_explanation,background_query,visual_style,music_file,metrics_json,
             reach,saved,shares,likes,comments,views,total_interactions)
            VALUES (:media_id,:snapshot_period,:target_at,:published_at,:scheduled_time,:captured_at,:topic_slug,
                    :hook_line,:ayah_key,:ayah_text,:iraqi_explanation,:background_query,:visual_style,:music_file,:metrics_json,
                    :reach,:saved,:shares,:likes,:comments,:views,:total_interactions)
            ON CONFLICT (media_id,snapshot_period) DO NOTHING
    """), values)
    return result.rowcount == 1


def _persist_learning(session, row: dict, period: str, metrics: dict,
                      captured_at: datetime) -> None:
    """Persist period-specific signals: the weekly planner can compare like with like."""
    from phase8_learning.database.models import LearningObservationModel

    context = {
        "media_id": str(row["media_id"]), "snapshot_period": period,
        "captured_at": captured_at.isoformat(), "topic_slug": row.get("topic_slug", ""),
        "scheduled_time": row.get("scheduled_time", ""),
        "published_at": row.get("published_at", ""),
        "date": row.get("date", ""),
        "hook_line": row.get("hook_line", ""), "ayah_key": row.get("ayah_key", ""),
        "ayah_text": row.get("ayah_text", ""),
        "iraqi_explanation": row.get("iraqi_explanation", ""),
        "background_query": row.get("background_query", ""),
        "visual_style": row.get("visual_style", ""), "music_file": row.get("music_file", ""),
    }
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


def fetch_optional_reels_retention(ig, media_id, product_type, deadline):
    """Return Reel-only estimates without jeopardizing already-read core metrics."""
    if product_type != "REELS":
        return {}
    result = dict.fromkeys(REELS_RETENTION_METRICS)
    for metric in REELS_RETENTION_METRICS:
        if (deadline - datetime.now(timezone.utc)).total_seconds() <= RETENTION_TIMEOUT_SECONDS:
            break
        try:
            # Request independently: an unsupported skip rate must not hide watch time.
            response = ig._request(
                "GET", f"{media_id}/insights",
                params={"metric": metric},
                timeout=RETENTION_TIMEOUT_SECONDS,
            )
        except (InstagramAPIError, RequestException, ValueError):
            continue
        if datetime.now(timezone.utc) > deadline:
            break
        items = response.get("data") if isinstance(response, dict) else None
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or item.get("name") != metric:
                continue
            values = item.get("values")
            if not isinstance(values, list) or not values or not isinstance(values[0], dict):
                continue
            value = values[0].get("value")
            if type(value) in (int, float) and math.isfinite(value) and value >= 0:
                result[metric] = value
                break
    return result


def _initialize_learning():
    from phase8_learning.config.settings import Settings
    from phase8_learning.database.connection import DatabaseConnectionFactory
    factory = DatabaseConnectionFactory(Settings.from_env())
    ensure_snapshot_table(factory.engine)
    return factory


def main():
    config.check_required_env_vars(["GOOGLE_SHEET_ID", "IG_ACCESS_TOKEN", "IG_BUSINESS_ID"])
    sheets = SheetsClient(config.load_sheets_service_account_json(), config.require_env("GOOGLE_SHEET_ID"))
    if sheets.is_paused():
        print("System is paused. Exiting.")
        return

    ig = InstagramClient(config.require_env("IG_ACCESS_TOKEN"), config.require_env("IG_BUSINESS_ID"))
    factory = _initialize_learning()
    fetched = 0
    failed = 0
    seen = set()
    try:
        from phase8_learning.database.models import LearningObservationModel

        LearningObservationModel.__table__.create(factory.engine, checkfirst=True)
        daily_rows = sheets._ws(config.DAILY_LOG_TAB).get_all_records()  # noqa: SLF001
        for row_index, row in enumerate(daily_rows, start=2):
            if row.get("status") not in (config.STATUS_PUBLISHED, config.STATUS_CLEANED):
                continue
            published_at = _parse_datetime(row.get("published_at"))
            media_id = str(row.get("media_id") or "").strip()
            if not published_at or not media_id or media_id in seen:
                continue
            seen.add(media_id)
            now = datetime.now(timezone.utc)
            candidates = [
                (period, published_at + timedelta(hours=hours))
                for period, hours in MILESTONES
                if published_at + timedelta(hours=hours) <= now
                <= published_at + timedelta(hours=hours) + MAX_SNAPSHOT_DELAY
            ]
            if not candidates:
                continue
            period, target_at = candidates[0]
            try:
                if period in _read_snapshots(factory.engine, media_id):
                    continue
                metrics, media_type = fetch_media_insights(ig, media_id)
                if metrics is None:
                    print(f"Skipping unsupported media in row {row_index} ({media_type})")
                    continue
                captured_at = datetime.now(timezone.utc)
                if captured_at > target_at + MAX_SNAPSHOT_DELAY:
                    continue
                if not isinstance(metrics.get("reach"), (int, float)):
                    raise RuntimeError("Instagram did not return reach")
                # Only the comparable 24h checkpoint needs extra API requests.
                retention = (
                    fetch_optional_reels_retention(
                        ig, media_id, media_type, target_at + MAX_SNAPSHOT_DELAY
                    )
                    if period == "24h" else {}
                )
                row = {**row, "media_id": media_id}
                with factory.new_session() as session, session.begin():
                    if not _save_snapshot(session, row, period, target_at, captured_at, {**metrics, **retention}):
                        continue
                    _persist_learning(session, row, period, metrics, captured_at)
                fetched += 1
            except Exception as exc:
                failed += 1
                print(f"Could not measure row {row_index}/{period}: {type(exc).__name__}")
                continue
            try:
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
                    "background_query": row.get("background_query", ""),
                    "music_file": row.get("music_file", ""), "visual_style": row.get("visual_style", ""),
                })
            except Exception as exc:
                print(f"Database saved row {row_index}/{period}; sheet mirror failed: {type(exc).__name__}")
    finally:
        factory.engine.dispose()
    if failed:
        raise SystemExit(f"{failed} due measurements failed; {fetched} saved.")
    print(f"Saved {fetched} milestone snapshot(s); schedule: 1h, 2h, 6h, 24h, 3d, 7d.")


if __name__ == "__main__":
    main()
