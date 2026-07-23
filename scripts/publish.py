"""
Publisher — runs every 15 minutes. Finds Daily_Log rows that are ready
and due, publishes them directly via the Instagram Graph API, updates status.
"""
import os
import sys
from datetime import datetime

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib import config
from lib.error_handler import CriticalError, handle_unexpected
from lib.gemini_client import GeminiClient
from lib.instagram_client import InstagramClient, InstagramAPIError
from lib.drive_client import DriveClient
from lib.sheets_client import SheetsClient
from lib.telegram_notifier import TelegramNotifier

REQUIRED_VARS = [
    "GOOGLE_SHEET_ID", "GOOGLE_DRIVE_FOLDER_ID",
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

    ig_token = config.require_env("IG_ACCESS_TOKEN")
    ig_business_id = config.require_env("IG_BUSINESS_ID")
    ig = InstagramClient(ig_token, ig_business_id)

    if not ig.verify_token():
        notifier.alert_critical(
            "توكن Instagram متوقف أو غير صالح",
            "فشل نشر أي منشور حتى يُصلح التوكن يدوياً. تحقق من IG_ACCESS_TOKEN.",
        )
        sys.exit(1)

    now_iso = datetime.utcnow().isoformat()
    due_posts = sheets.get_ready_posts_due_now(now_iso)

    if not due_posts:
        print("No posts due right now.")
        return

    drive = DriveClient(config.load_drive_oauth_token_json(), config.require_env("GOOGLE_DRIVE_FOLDER_ID"))
    gemini_keys = [config.optional_env("GEMINI_API_KEY_1"), config.optional_env("GEMINI_API_KEY_2"), config.optional_env("GEMINI_API_KEY_3")]
    gemini = GeminiClient(gemini_keys) if any(gemini_keys) else None
    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    for row_index, row in due_posts:
        try:
            # Reserve this row FIRST, before touching the Instagram API.
            # This is the critical ordering fix: previously the row was only
            # marked "published" AFTER the Instagram call succeeded, so if
            # that final Sheets write failed for any reason (quota, a race,
            # a bug), the row silently stayed "ready" and got published
            # again on the very next 15-minute run — real duplicate posts
            # on Instagram, repeating forever since the same write kept
            # failing the same way each time.
            try:
                sheets.update_row_fields(
                    config.DAILY_LOG_TAB, row_index,
                    {"status": config.STATUS_PUBLISHING, "reserved_at": datetime.utcnow().isoformat()},
                    verify_field="topic_slug", verify_value=row.get("topic_slug"),
                )
            except Exception as e:
                # Couldn't even reserve it — do NOT call Instagram. Skip this
                # row this run; it's still "ready" so it'll be retried next
                # run once whatever's wrong with Sheets clears up.
                print(f"⚠️ Could not reserve {row.get('topic_slug')} for publishing, skipping this run: {e}")
                continue

            public_url = drive.get_public_download_url(row["drive_file_id"])
            if not drive.verify_video_link_ready(public_url):
                raise InstagramAPIError(
                    f"Drive link for {row.get('topic_slug')} never resolved to a video "
                    f"(possibly Drive's virus-scan HTML page, or permissions not yet public). "
                    f"URL: {public_url}"
                )
            caption = row.get("caption_arabic", "")
            hashtags = row.get("hashtags", "")
            full_caption = f"{caption}\n\n{hashtags}".strip()

            media_id = ig.publish_reel(public_url, full_caption)

            try:
                sheets.update_row_fields(
                    config.DAILY_LOG_TAB, row_index,
                    {
                        "status": config.STATUS_PUBLISHED,
                        "published_at": datetime.utcnow().isoformat(),
                        "media_id": media_id,
                    },
                    verify_field="topic_slug", verify_value=row.get("topic_slug"),
                )
            except Exception as e:
                # The post IS live on Instagram at this point (media_id
                # exists) — we must NOT let this row fall back to "ready"
                # or it would be published a second time next run. It stays
                # "publishing" and shows up in the stale-row alert below, so
                # a human can finish the sheet update by hand.
                notifier.alert_critical(
                    f"⚠️ نُشر المنشور {row.get('topic_slug')} على انستغرام بنجاح (media_id={media_id}) "
                    f"لكن فشل تحديث الشيت بعدها",
                    f"حدّث يدوياً: status=published, published_at, media_id={media_id} للصف رقم {row_index}. الخطأ: {e}",
                )
                continue

            print(f"✓ Published post {row.get('topic_slug')} -> media_id={media_id}")

        except InstagramAPIError as e:
            # Known, external failure category — plain alert, no auto-fix attempt.
            # Roll the reservation back to "ready" since Instagram was never
            # actually called successfully, so the next run can retry it.
            try:
                sheets.update_row_fields(
                    config.DAILY_LOG_TAB, row_index, {"status": config.STATUS_READY, "reserved_at": ""},
                    verify_field="topic_slug", verify_value=row.get("topic_slug"),
                )
            except Exception:
                pass
            notifier.alert_critical(
                f"فشل نشر منشور: {row.get('topic_slug', 'unknown')}",
                str(e),
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            # Transient network failure while calling Instagram. We don't
            # know for certain whether the post went through, so — unlike
            # before — we do NOT roll back to "ready" here; that would risk
            # a duplicate if it actually succeeded. It stays "publishing"
            # and will surface via the stale-row check if it's really stuck.
            print(f"⚠️ Transient network error publishing {row.get('topic_slug')}, left as 'publishing' for manual check: {e}")
        except Exception:
            # Anything unanticipated — route through Gemini diagnosis + PR flow.
            if gemini:
                handle_unexpected(
                    notifier, gemini,
                    config.optional_env("GH_PAT"), config.optional_env("GH_REPO"),
                    "scripts/publish.py", f"publish loop, row {row_index}: {row.get('topic_slug', 'unknown')}", date_str,
                )
            else:
                notifier.alert_critical(
                    f"خطأ غير متوقع أثناء النشر (بدون مفاتيح Gemini للتشخيص الآلي): {row.get('topic_slug', 'unknown')}",
                    "لم يتم إعداد GEMINI_API_KEY_1 كسر — تعذّر إنشاء اقتراح إصلاح آلي.",
                )

    # Surface any row that's been reserved too long without confirming —
    # these are exactly the cases that used to silently duplicate.
    stale = sheets.get_stale_publishing_rows(config.STALE_PUBLISHING_MINUTES)
    for row_index, row in stale:
        notifier.alert_critical(
            f"⏳ منشور عالق بحالة 'publishing' منذ أكثر من {config.STALE_PUBLISHING_MINUTES} دقيقة: {row.get('topic_slug')}",
            f"تحقق يدوياً هل نُشر فعلاً على انستغرام قبل أي إجراء (الصف رقم {row_index}). "
            f"لن يُعاد نشره تلقائياً لتفادي التكرار.",
        )


if __name__ == "__main__":
    main()
