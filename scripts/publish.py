"""
Publisher — runs every 15 minutes. Finds Daily_Log rows that are ready
and due, publishes them directly via the Instagram Graph API, updates status.
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib import config
from lib.error_handler import CriticalError
from lib.instagram_client import InstagramClient, InstagramAPIError
from lib.drive_client import DriveClient
from lib.sheets_client import SheetsClient
from lib.telegram_notifier import TelegramNotifier

REQUIRED_VARS = [
    "GOOGLE_SERVICE_ACCOUNT_JSON", "GOOGLE_SHEET_ID", "GOOGLE_DRIVE_FOLDER_ID",
    "IG_ACCESS_TOKEN", "IG_BUSINESS_ID",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
]


def main():
    config.check_required_env_vars(REQUIRED_VARS)

    notifier = TelegramNotifier(config.require_env("TELEGRAM_BOT_TOKEN"), config.require_env("TELEGRAM_CHAT_ID"))
    sheets = SheetsClient(config.require_env("GOOGLE_SERVICE_ACCOUNT_JSON"), config.require_env("GOOGLE_SHEET_ID"))

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

    drive = DriveClient(config.require_env("GOOGLE_SERVICE_ACCOUNT_JSON"), config.require_env("GOOGLE_DRIVE_FOLDER_ID"))

    for row_index, row in due_posts:
        try:
            public_url = drive.get_public_download_url(row["drive_file_id"])
            caption = row.get("caption_arabic", "")
            hashtags = row.get("hashtags", "")
            full_caption = f"{caption}\n\n{hashtags}".strip()

            media_id = ig.publish_reel(public_url, full_caption)

            sheets.update_row_field(config.DAILY_LOG_TAB, row_index, "status", config.STATUS_PUBLISHED)
            sheets.update_row_field(config.DAILY_LOG_TAB, row_index, "published_at", datetime.utcnow().isoformat())

            print(f"✓ Published post {row.get('topic_slug')} -> media_id={media_id}")

        except InstagramAPIError as e:
            notifier.alert_critical(
                f"فشل نشر منشور: {row.get('topic_slug', 'unknown')}",
                str(e),
            )
        except Exception as e:
            notifier.alert_critical(
                f"خطأ غير متوقع أثناء النشر: {row.get('topic_slug', 'unknown')}",
                str(e),
            )


if __name__ == "__main__":
    main()
