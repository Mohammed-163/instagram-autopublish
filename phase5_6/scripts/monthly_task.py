"""Create the next Sunday-to-Saturday plan from measured Supabase performance."""
from __future__ import annotations

import os
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import median

import pytz

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib import config
from lib.audience_strategy import recommend
from lib.curated_hadith import HADITH_STYLE
from lib.gemini_client import GeminiClient
from lib.hook_experiment import base_visual_style
from lib.quran_content import load_verses, sunday_of
from lib.sheets_client import SheetsClient
from lib.telegram_notifier import TelegramNotifier


REQUIRED_VARS = [
    "GOOGLE_SHEET_ID", "GOOGLE_SERVICE_ACCOUNT_JSON_B64", "GEMINI_API_KEY_1",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
]
POSTS_PER_WEEK = 10
DAY_COUNTS = (2, 1, 2, 1, 2, 1, 1)  # Sunday, Tuesday and Thursday get a second slot
MIN_POSTS_PER_HOUR = 3
DEFAULT_SINGLE_TIME = "18:00"
DEFAULT_DOUBLE_TIMES = ("13:00", "18:00")


def load_supabase_performance_summary(*, include_editorial_metadata: bool = False) -> dict:
    """Aggregate actual Instagram metrics already stored by Phase 8 in Supabase."""
    if not any(os.getenv(key) for key in ("LEARNING_LAYER_DATABASE_URL", "DATABASE_URL", "SUPABASE_URL")):
        raise RuntimeError("Supabase/Postgres connection is required; configure LEARNING_LAYER_DATABASE_URL or DATABASE_URL or SUPABASE_URL.")
    from phase8_learning.config.settings import Settings
    from phase8_learning.database.connection import DatabaseConnectionFactory
    from sqlalchemy import inspect, text
    from phase5_6.scripts.fetch_insights import MAX_SNAPSHOT_DELAY

    factory = DatabaseConnectionFactory(Settings.from_env())
    posts = []
    try:
        if inspect(factory.engine).has_table("instagram_insight_snapshots"):
            with factory.engine.connect() as connection:
                rows = connection.execute(text("""
                    SELECT media_id, topic_slug, ayah_key, visual_style, music_file, hook_line,
                           background_query, scheduled_time, published_at, target_at, captured_at,
                           reach, views, saved, shares, likes, comments
                    FROM instagram_insight_snapshots
                    WHERE snapshot_period = '24h' AND reach > 0 AND published_at >= :since
                      AND (visual_style IS NULL OR visual_style <> :hadith_style)
                    ORDER BY published_at DESC
                """), {
                    "since": datetime.now(timezone.utc) - timedelta(days=90),
                    "hadith_style": HADITH_STYLE,
                }).mappings()
                for item in rows:
                    target = _parse_local_datetime(item["target_at"])
                    capture = _parse_local_datetime(item["captured_at"])
                    if not target or not capture or not target <= capture <= target + MAX_SNAPSHOT_DELAY:
                        continue
                    weighted = sum(
                        weight * (item[metric] or 0)
                        for metric, weight in (("saved", 3), ("shares", 2), ("comments", 1), ("likes", 1))
                    )
                    posts.append({
                        "media_id": item["media_id"],
                        "topic": item["topic_slug"],
                        "ayah_key": item["ayah_key"],
                        "visual_style": base_visual_style(item["visual_style"]),
                        "music": item["music_file"],
                        "hook": item["hook_line"],
                        "background_query": item["background_query"],
                        "scheduled_time": str(item["scheduled_time"] or ""),
                        "published_at": str(item["published_at"]),
                        "measured_24h": True,
                        "reach": item["reach"],
                        "views": item["views"],
                        "saved": item["saved"],
                        "shares": item["shares"],
                        "likes": item["likes"],
                        "comments": item["comments"],
                        "score": round(weighted / (item["reach"] + 20), 6),
                    })
                    if include_editorial_metadata:
                        posts[-1].update(raw_visual_style=item["visual_style"], captured_at=str(item["captured_at"]))

        posts.sort(key=lambda row: (row["score"], row["reach"], row["media_id"]), reverse=True)
        by_style: dict[str, list[float]] = defaultdict(list)
        by_music: dict[str, list[float]] = defaultdict(list)
        by_hook: dict[str, list[float]] = defaultdict(list)
        by_background: dict[str, list[float]] = defaultdict(list)
        for post in posts:
            if not post["measured_24h"]:
                continue
            if post["visual_style"]:
                by_style[post["visual_style"]].append(post["score"])
            if post["music"]:
                by_music[post["music"]].append(post["score"])
            if post["hook"]:
                by_hook[post["hook"]].append(post["score"])
            if post["background_query"]:
                by_background[post["background_query"]].append(post["score"])

        def averages(groups: dict[str, list[float]]) -> list[dict]:
            return [
                {"name": name, "posts": len(scores), "average_score": round(sum(scores) / len(scores), 6)}
                for name, scores in sorted(groups.items(), key=lambda pair: (-sum(pair[1]) / len(pair[1]), pair[0]))
            ]

        mature_music = averages(by_music)
        eligible_music = [item for item in mature_music if item["posts"] >= 3]
        best_music_score = max((item["average_score"] for item in eligible_music), default=0.0)
        music_weights = {
            item["name"]: round(max(0.5, item["average_score"] / best_music_score), 3)
            if best_music_score > 0 else 1.0
            for item in eligible_music
        }

        return {
            "source": "Supabase on-time 24-hour Instagram snapshots (last 90 days)",
            "sample_size": len(posts),
            "score_definition": "(3*saved + 2*shares + comments + likes) / (reach + 20)",
            "top_posts": posts[:5],
            "top_by_views": sorted(posts, key=lambda row: row["views"] or 0, reverse=True)[:5],
            "bottom_posts": list(reversed(posts[-5:])),
            "_all_posts": posts,
            "by_visual_style": averages(by_style),
            "by_music": averages(by_music),
            "music_weights": music_weights,
            "by_hook": averages(by_hook),
            "by_background_query": averages(by_background),
        }
    finally:
        factory.engine.dispose()


def _parse_local_datetime(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = pytz.utc.localize(parsed)
    return parsed.astimezone(pytz.timezone(config.BAGHDAD_TZ))


def choose_publishing_times(posts: list[dict], current_week_start: date) -> dict:
    """Compare Baghdad posting hours using recent, comparable snapshots."""
    previous_start = current_week_start - timedelta(weeks=4)
    hours: dict[int, list[dict]] = defaultdict(list)
    for post in posts:
        if not post.get("measured_24h") or (post.get("reach") or 0) <= 0:
            continue
        published = _parse_local_datetime(post.get("published_at"))
        if published is None or not (previous_start <= published.date() < current_week_start):
            continue
        hours[published.hour].append(post)

    observed_posts = sum(len(values) for values in hours.values())
    qualified = {}
    for hour, values in hours.items():
        if len(values) < MIN_POSTS_PER_HOUR:
            continue
        views = [post["views"] for post in values if post.get("views") is not None]
        qualified[hour] = {
            "posts": len(values),
            "score": sum(post["score"] for post in values) / len(values),
            "reach": sum(post["reach"] for post in values),
            "median_views": median(views) if len(views) >= MIN_POSTS_PER_HOUR else None,
        }
    if len(qualified) < 2:
        return {"source": "standard_fallback", "sample_size": observed_posts,
                "single": DEFAULT_SINGLE_TIME, "double": list(DEFAULT_DOUBLE_TIMES), "hour_stats": qualified}

    compare_views = all(item["median_views"] is not None for item in qualified.values())
    ranked = sorted(qualified, key=lambda hour: (
        qualified[hour]["median_views"] if compare_views else qualified[hour]["score"],
        qualified[hour]["score"], qualified[hour]["reach"], -hour,
    ), reverse=True)
    best_pair = sorted(ranked[:2])
    return {"source": "last_four_weeks_24h_performance", "sample_size": observed_posts,
            "single": f"{ranked[0]:02d}:00",
            "double": [f"{hour:02d}:00" for hour in best_pair], "hour_stats": qualified}


def _build_rows(posts: list[dict], week_start: date, time_policy: dict | None = None,
                music_weights: dict[str, float] | None = None) -> list[list[str]]:
    verses = load_verses()
    if len(verses) < POSTS_PER_WEEK:
        raise ValueError("The verse catalogue must contain at least ten unique ayat.")
    # Deterministic rotation makes reruns of the same week's plan idempotent.
    offset = week_start.toordinal() % len(verses)
    selected_verses = verses[offset:] + verses[:offset]
    topics = posts[:POSTS_PER_WEEK]
    if len(topics) != POSTS_PER_WEEK:
        raise ValueError("The weekly strategy must contain exactly ten topics.")

    rows: list[list[str]] = []
    time_policy = time_policy or {"single": DEFAULT_SINGLE_TIME, "double": list(DEFAULT_DOUBLE_TIMES)}
    topic_index = 0
    for day_index, post_count in enumerate(DAY_COUNTS):
        day = week_start + timedelta(days=day_index)
        slots: list[tuple[str, str, str, str, str]] = []
        for slot_index in range(post_count):
            planned = topics[topic_index]
            verse = selected_verses[topic_index]
            local_time = (time_policy["double"][slot_index] if post_count == 2
                          else time_policy["single"])
            slots.append((local_time, str(planned.get("pixabay_query") or "peaceful nature sunrise"),
                          str(planned["topic"]).strip(), str(verse["key"]),
                          str(planned.get("hook_guidance") or "اكتب هوكاً عراقياً قصيراً مناسباً لموضوع المنشور من دون نسخ أمثلة سابقة.")))
            topic_index += 1

        # Existing columns retained for compatibility; topic and ayah get dedicated columns.
        row = [day.isoformat(), str(post_count)]
        for post_number in range(1, 4):
            if post_number <= len(slots):
                time_text, query, _, _, _ = slots[post_number - 1]
                row.extend(["reel", time_text, query, ""])
            else:
                row.extend(["", "", "", ""])
        row.extend([slots[i][2] if i < len(slots) else "" for i in range(3)])
        row.extend([slots[i][3] if i < len(slots) else "" for i in range(3)])
        row.extend([slots[i][4] if i < len(slots) else "" for i in range(3)])
        row.append(json.dumps(music_weights or {}, ensure_ascii=False, sort_keys=True))
        rows.append(row)
    if topic_index != POSTS_PER_WEEK:
        raise AssertionError(f"Plan assigned {topic_index} posts instead of {POSTS_PER_WEEK}.")
    return rows


def audience_report(posts: list[dict], week_start: date, *, private_preview: bool = False) -> dict:
    # Recommendation only; no mutation, paid model call, or write to the queue.
    report = recommend(posts, week_start, {verse["key"] for verse in load_verses()})
    if private_preview:
        print("Audience strategy (shadow): " + json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        # This repository has public Actions logs. Do not print insights or draft hooks here.
        print("Audience strategy shadow preview checked; no production changes.")
    return report


def main() -> None:
    if sys.argv[1:] == ["--audience-preview"]:
        week = sunday_of(datetime.now(pytz.timezone(config.BAGHDAD_TZ)).date()) + timedelta(days=7)
        posts = load_supabase_performance_summary(include_editorial_metadata=True)["_all_posts"]
        audience_report(posts, week, private_preview=True)
        return
    config.check_required_env_vars(REQUIRED_VARS)
    notifier = TelegramNotifier(config.require_env("TELEGRAM_BOT_TOKEN"), config.require_env("TELEGRAM_CHAT_ID"))
    sheets = SheetsClient(config.load_sheets_service_account_json(), config.require_env("GOOGLE_SHEET_ID"))
    if sheets.is_paused():
        print("System is paused. Exiting.")
        return

    try:
        now = datetime.now(pytz.timezone(config.BAGHDAD_TZ))
        week_start = sunday_of(now.date())
        print(f"Reading prior real performance from Supabase for plan starting {week_start}...")
        performance = load_supabase_performance_summary(include_editorial_metadata=True)
        print(f"Loaded {performance['sample_size']} measured Instagram posts from Supabase.")
        posts = performance.pop("_all_posts", [])
        time_policy = choose_publishing_times(posts, week_start)
        try:
            audience_report(posts, week_start)
        except Exception as exc:
            # Preview failures must not interrupt the ordinary plan or reveal secrets.
            print(f"Audience strategy preview unavailable: {type(exc).__name__}")
        for post in posts:
            # Shared references also occur in top_posts: don't alter the live
            # model prompt or teach it the opener experiment's internal labels.
            post.pop("raw_visual_style", None)
            post.pop("captured_at", None)
        music_weights = performance.get("music_weights", {})
        print(f"Publishing-time policy: {time_policy}")
        performance["publishing_time_policy"] = {
            key: value for key, value in time_policy.items() if key != "hour_stats"
        }

        gemini = GeminiClient([
            config.optional_env("GEMINI_API_KEY_1"),
            config.optional_env("GEMINI_API_KEY_2"),
            config.optional_env("GEMINI_API_KEY_3"),
        ])
        generated = gemini.build_weekly_content_plan(performance, week_start.isoformat())
        rows = _build_rows(generated["posts"], week_start, time_policy, music_weights)
        sheets.archive_and_reset_plan(rows, f"week-{week_start.isoformat()}")

        summary = [
            f"{row[0]}: {row[1]} منشور ({row[3]}" + (f" و {row[7]}" if row[1] == "2" else "") + ")"
            for row in rows
        ]
        notifier.notify_success(
            f"تم إنشاء الخطة الأسبوعية: 10 منشورات، بدءاً من {week_start.isoformat()}\n"
            f"عدد المنشورات التي قيّمها Supabase: {performance['sample_size']}\n" + "\n".join(summary)
        )
        print("Weekly plan saved. The daily generator will read these topics, verse references and Baghdad posting times.")
    except Exception as exc:
        notifier.alert_critical("فشل إنشاء الخطة الأسبوعية", str(exc))
        raise


if __name__ == "__main__":
    main()
