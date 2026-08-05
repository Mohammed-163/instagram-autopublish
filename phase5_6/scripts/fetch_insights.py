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


def main():
    config.check_required_env_vars(REQUIRED_VARS)

    notifier = TelegramNotifier(config.require_env("TELEGRAM_BOT_TOKEN"), config.require_env("TELEGRAM_CHAT_ID"))
    sheets = SheetsClient(config.load_sheets_service_account_json(), config.require_env("GOOGLE_SHEET_ID"))

    if sheets.is_paused():
        print("System is paused. Exiting.")
        return

    ig = InstagramClient(config.require_env("IG_ACCESS_TOKEN"), config.require_env("IG_BUSINESS_ID"))
    gemini_keys = [config.optional_env("GEMINI_API_KEY_1"), config.optional_env("GEMINI_API_KEY_2"), config.optional_env("GEMINI_API_KEY_3")]
    gemini = GeminiClient(gemini_keys) if any(gemini_keys) else None
    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    cutoff_iso = (datetime.utcnow() - timedelta(days=config.INSIGHTS_FETCH_DELAY_DAYS)).isoformat()
    due_posts = sheets.get_posts_due_for_insights(cutoff_iso)

    if not due_posts:
        print("No posts due for insights collection right now.")
        return

    fetched = 0
    for row_index, row in due_posts:
        try:
            metrics = ig.get_media_insights(row["media_id"])
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
            sheets.update_row_fields(
                config.DAILY_LOG_TAB, row_index,
                {"insights_fetched": "yes"},
                verify_field="topic_slug", verify_value=row.get("topic_slug"),
            )
            fetched += 1
            print(f"✓ Pulled insights for {row.get('topic_slug')} (media_id={row.get('media_id')})")

        except InstagramAPIError as e:
            # Media may have been deleted manually, or insights aren't ready
            # yet for some edge case — log and try again on the next run
            # rather than treating it as critical.
            print(f"⚠️ Could not fetch insights for {row.get('topic_slug')}: {e}")
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            print(f"⚠️ Transient network error fetching insights for {row.get('topic_slug')}, will retry next run: {e}")
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

    print(f"Fetched insights for {fetched}/{len(due_posts)} post(s).")


if __name__ == "__main__":
    main()
