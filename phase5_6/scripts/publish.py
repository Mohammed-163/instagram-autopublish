"""
Publisher — runs every 15 minutes. Finds Daily_Log rows that are ready
and due, publishes them directly via the Instagram Graph API, updates status.
"""
import os
import sys
import logging
from dataclasses import dataclass
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib import config
from lib.instagram_client import InstagramClient, InstagramAPIError
from lib.drive_client import DriveClient
from lib.sheets_client import SheetsClient
from lib.telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PostPublished:
    media_id: str
    topic_slug: str
    hook_line: str
    published_at: str
    media_type: str


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

    # Surface any row that's been reserved too long without confirming —
    # these are exactly the cases that used to silently duplicate.
    stale = sheets.get_stale_publishing_rows(config.STALE_PUBLISHING_MINUTES)
    for row_index, row in stale:
        notifier.alert_critical(
            f"⏳ منشور عالق بحالة 'publishing' منذ أكثر من {config.STALE_PUBLISHING_MINUTES} دقيقة: {row.get('topic_slug')}",
            f"تحقق يدوياً هل نُشر فعلاً على انستغرام قبل أي إجراء (الصف رقم {row_index}). "
            f"لن يُعاد نشره تلقائياً لتفادي التكرار.",
        )

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
    failed = 0
    for row_index, row in due_posts:
        publish_attempted = False
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
                print(f"⚠️ Could not reserve {row.get('topic_slug')} for publishing, skipping this run: {type(e).__name__}")
                failed += 1
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

            container_id = ig.create_reel_container(public_url, full_caption)
            ig.wait_for_container(container_id)
            publish_attempted = True
            media_id = ig.publish_container(container_id)
            published_at = datetime.utcnow().isoformat()

            try:
                sheets.update_row_fields(
                    config.DAILY_LOG_TAB, row_index,
                    {
                        "status": config.STATUS_PUBLISHED,
                        "published_at": published_at,
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
                    f"حدّث يدوياً: status=published, published_at, media_id={media_id} للصف رقم {row_index}. الخطأ: {type(e).__name__}",
                )
                failed += 1
                continue

            try:
                post_published = PostPublished(
                    media_id=str(media_id),
                    topic_slug=str(row.get("topic_slug") or ""),
                    hook_line=str(row.get("hook_line") or ""),
                    published_at=published_at,
                    media_type="REELS",
                )
                logger.info(
                    "post_published media_id=%s topic_slug=%s hook_line=%s "
                    "published_at=%s media_type=%s",
                    post_published.media_id,
                    post_published.topic_slug,
                    post_published.hook_line,
                    post_published.published_at,
                    post_published.media_type,
                )
            except Exception:
                logger.exception(
                    "Failed to log post_published event (non-critical)"
                )

            print(f"✓ Published post {row.get('topic_slug')} -> media_id={media_id}")

        except Exception as exc:
            failed += 1
            if not publish_attempted:
                try:
                    sheets.update_row_fields(
                        config.DAILY_LOG_TAB, row_index,
                        {"status": config.STATUS_READY, "reserved_at": ""},
                        verify_field="topic_slug", verify_value=row.get("topic_slug"),
                    )
                except Exception:
                    logger.warning("Could not release publication reservation for row %s", row_index)
            notifier.alert_critical(
                f"فشل نشر الصف {row_index}",
                ("تحقق من حساب Instagram قبل إعادة المحاولة. " if publish_attempted else "")
                + type(exc).__name__,
            )
    if failed:
        raise SystemExit(f"{failed}/{len(due_posts)} due publications did not complete.")


if __name__ == "__main__":
    main()
