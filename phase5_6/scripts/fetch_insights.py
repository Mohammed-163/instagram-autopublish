"""
Insights fetcher — runs once a day.

For every post in Daily_Log that:
  - is published (or already cleaned), AND
  - was published at least config.INSIGHTS_FETCH_DELAY_DAYS ago, AND
  - hasn't had insights_fetched='yes' yet (this also naturally sweeps up any
    older posts that were missed by a previous run for any reason)

...pulls reach/saved/shares/likes/comments from the Instagram Graph API and
appends a row to the dedicated Post_Performance sheet tab, then marks the
Daily_Log row as insights_fetched='yes' so it's never re-pulled.

Post_Performance is what scripts/monthly_task.py now hands to Gemini when
building next month's plan, so content decisions are driven by which
topics/angles actually performed — not just raw last-30-days media stats.
"""
import os
import sys
import uuid
from datetime import datetime, timedelta

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib import config
from lib.error_handler import handle_unexpected
from lib.gemini_client import GeminiClient
from lib.instagram_client import InstagramClient, InstagramAPIError
from lib.sheets_client import SheetsClient
from lib.telegram_notifier import TelegramNotifier

REQUIRED_VARS = [
    "GOOGLE_SHEET_ID",
    "IG_ACCESS_TOKEN", "IG_BUSINESS_ID",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
]

INSIGHTS_METRICS = "reach,saved,likes,comments,shares,views"
SUPPORTED_MEDIA_PRODUCT_TYPES = {"FEED", "REELS", "CAROUSEL_ALBUM"}


def fetch_media_insights(ig, media_id):
    """Fetch media metadata, then query the Insights edge independently."""
    metadata = ig._request(  # noqa: SLF001 - no public metadata/edge method exists
        "GET", str(media_id), params={"fields": "media_product_type,media_type"}
    )
    media_product_type = str(metadata.get("media_product_type") or "UNKNOWN").upper()
    media_type = str(metadata.get("media_type") or "").upper()

    # Carousel children are IMAGE/VIDEO objects, not the CAROUSEL_ALBUM container.
    if media_type in {"IMAGE", "VIDEO"} and media_product_type not in SUPPORTED_MEDIA_PRODUCT_TYPES:
        return None, media_product_type

    if media_product_type not in SUPPORTED_MEDIA_PRODUCT_TYPES and media_type != "CAROUSEL_ALBUM":
        raise InstagramAPIError(
            f"unsupported media type: media_product_type={media_product_type}, "
            f"media_type={media_type or 'UNKNOWN'}"
        )

    data = ig._request(  # noqa: SLF001 - Insights is an edge, not a media field
        "GET", f"{media_id}/insights", params={"metric": INSIGHTS_METRICS}
    )
    result = {}
    for item in data.get("data", []):
        values = item.get("values", [])
        result[item["name"]] = values[0].get("value") if values else None
    return result, media_product_type


def resolve_published_media_id(ig, row):
    """Resolve stale container IDs to the final published Instagram media ID."""
    media = ig._request(
        "GET", f"{ig.ig_business_id}/media",
        params={"fields": "id,caption,timestamp,media_type,media_product_type,shortcode,permalink", "limit": 100},
    ).get("data", [])
    stored_id = str(row.get("media_id") or "")
    for item in media:
        if str(item.get("id")) == stored_id:
            return item["id"]

    topic = str(row.get("topic_slug") or "").lower()
    hook = str(row.get("hook_line") or "").lower()
    candidates = [
        item for item in media
        if (topic and topic in str(item.get("caption") or "").lower())
        or (hook and hook in str(item.get("caption") or "").lower())
    ]
    if len(candidates) == 1:
        return candidates[0]["id"]
    raise InstagramAPIError(
        f"stored media_id {stored_id!r} was not found and no unique published media matched "
        f"topic_slug={topic!r}"
    )


def main():
    config.check_required_env_vars(REQUIRED_VARS)

    notifier = TelegramNotifier(config.require_env("TELEGRAM_BOT_TOKEN"), config.require_env("TELEGRAM_CHAT_ID"))
    sheets = SheetsClient(config.load_sheets_service_account_json(), config.require_env("GOOGLE_SHEET_ID"))

    if sheets.is_paused():
        print("System is paused. Exiting.")
        return

    ig = InstagramClient(config.require_env("IG_ACCESS_TOKEN"), config.require_env("IG_BUSINESS_ID"))

    phase7_bootstrap = None
    try:
        import phase7_observation  # noqa: F401 — adds Phase 7 to sys.path
        from observation.application.bootstrap import ApplicationBootstrap
        from observation.config import load_settings as load_observation_settings
        from bridges.observation_to_learning import wire as wire_observation_learning
        from phase8_learning.main import run as phase8_run

        phase7_bootstrap = ApplicationBootstrap(load_observation_settings())
        wire_observation_learning(
            phase7_bootstrap.in_process_publisher,
            phase8_run,
        )
        print("Phase 7 → Phase 8 observation bridge enabled.")
    except Exception as e:
        print(
            "⚠️ Phase 7/8 bridge unavailable; continuing with Sheets only: "
            f"{e}"
        )

    gemini_keys = [config.optional_env("GEMINI_API_KEY_1"), config.optional_env("GEMINI_API_KEY_2"), config.optional_env("GEMINI_API_KEY_3")]
    gemini = GeminiClient(gemini_keys) if any(gemini_keys) else None
    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    # Direct account pull: do not filter by stale/old Daily_Log media IDs.
    # Sheets remains an optional metadata/update store only.
    daily_rows = sheets._ws(config.DAILY_LOG_TAB).get_all_records()  # noqa: SLF001
    live_media = ig._request(
        "GET", f"{ig.ig_business_id}/media",
        params={"fields": "id,caption,timestamp,media_type,media_product_type", "limit": 100},
    ).get("data", [])
    live_work = []
    for item in live_media:
        item_id = str(item.get("id") or "")
        caption = str(item.get("caption") or "").lower()
        matches = [
            (row_index, row) for row_index, row in enumerate(daily_rows, start=2)
            if item_id == str(row.get("media_id") or "")
            or (
                row.get("topic_slug")
                and str(row.get("topic_slug")).lower() in caption
            )
        ]
        row_index, row = matches[0] if matches else (None, {})
        live_work.append((row_index, {
            **row,
            "media_id": item_id,
            "caption": item.get("caption", ""),
            "topic_slug": row.get("topic_slug") or item.get("caption", ""),
        }))

    fetched = 0
    for row_index, row in live_work:
        media_product_type = "UNKNOWN"
        try:
            resolved_media_id = row["media_id"]
            metrics, media_product_type = fetch_media_insights(ig, resolved_media_id)
            if metrics is None:
                print(
                    f"⚠️ Skipping carousel child {row.get('topic_slug')} "
                    f"(media_id={resolved_media_id}, type: {media_product_type})"
                )
                continue
            sheets.append_post_performance({
                "date": row.get("date", ""),
                "topic_slug": row.get("topic_slug", ""),
                "hook_line": row.get("hook_line", ""),
                "fact_line": row.get("fact_line", ""),
                "caption_arabic": row.get("caption_arabic", ""),
                "hashtags": row.get("hashtags", ""),
                "media_id": row.get("media_id", ""),
                "published_at": row.get("published_at", ""),
                "fetched_at": datetime.utcnow().isoformat(),
                "reach": metrics.get("reach", ""),
                "saved": metrics.get("saved", ""),
                "shares": metrics.get("shares", ""),
                "likes": metrics.get("likes", ""),
                "comments": metrics.get("comments", ""),
            })
            if phase7_bootstrap is not None:
                try:
                    from observation.domain.events import ExecutionCompleted

                    phase7_bootstrap.handle_event(
                        ExecutionCompleted(
                            execution_id=str(uuid.uuid4()),
                            workflow_id="fetch_insights",
                            node_id=row.get("topic_slug", "unknown"),
                            tenant_id="system",
                            payload={"result": {
                                "reach": metrics.get("reach"),
                                "saved": metrics.get("saved"),
                                "likes": metrics.get("likes"),
                                "comments": metrics.get("comments"),
                                "shares": metrics.get("shares"),
                                "topic_slug": row.get("topic_slug", ""),
                                "hook_line": row.get("hook_line", ""),
                            }},
                        )
                    )
                except Exception as e:
                    print(
                        "⚠️ Phase 7/8 processing failed; Sheets write succeeded "
                        f"for {row.get('topic_slug')}: {e}"
                    )
            if row_index is not None:
                sheets.update_row_fields(
                    config.DAILY_LOG_TAB, row_index,
                    {"insights_fetched": "yes"},
                    verify_field="topic_slug", verify_value=row.get("topic_slug"),
                )
            fetched += 1
            print(f"✓ Pulled insights for {row.get('topic_slug')} (media_id={resolved_media_id})")

        except InstagramAPIError as e:
            # Media may have been deleted manually, or insights aren't ready
            # yet for some edge case — log and try again on the next run
            # rather than treating it as critical.
            print(
                f"⚠️ Could not fetch insights for {row.get('topic_slug')} "
                f"(type: {media_product_type}): {e}"
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            print(
                f"⚠️ Transient network error fetching insights for {row.get('topic_slug')} "
                f"(type: {media_product_type}), will retry next run: {e}"
            )
        except Exception:
            if gemini:
                handle_unexpected(
                    notifier, gemini,
                    config.optional_env("GH_PAT"), config.optional_env("GH_REPO"),
                    "scripts/fetch_insights.py", f"insights loop, row {row_index}: {row.get('topic_slug', 'unknown')}", date_str,
                )
            else:
                notifier.alert_critical(
                    f"خطأ غير متوقع أثناء جلب بيانات الأداء (بدون مفاتيح Gemini للتشخيص الآلي): {row.get('topic_slug', 'unknown')}",
                    "لم يتم إعداد GEMINI_API_KEY_1 — تعذّر إنشاء اقتراح إصلاح آلي.",
                )

    if phase7_bootstrap is not None:
        phase7_bootstrap.shutdown()

    print(f"Fetched insights for {fetched}/{len(live_work)} post(s).")


if __name__ == "__main__":
    main()
