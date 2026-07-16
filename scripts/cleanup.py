"""
Cleanup — runs every 30 minutes. Deletes videos from Drive for posts that
were published 2+ hours ago (status-based, not a blind fixed-time delete).
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib import config
from lib.drive_client import DriveClient
from lib.sheets_client import SheetsClient
from lib.telegram_notifier import TelegramNotifier

REQUIRED_VARS = [
    "GOOGLE_SHEET_ID", "GOOGLE_DRIVE_FOLDER_ID",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
]


def main():
    config.check_required_env_vars(REQUIRED_VARS)

    notifier = TelegramNotifier(config.require_env("TELEGRAM_BOT_TOKEN"), config.require_env("TELEGRAM_CHAT_ID"))
    sheets = SheetsClient(config.load_service_account_json(), config.require_env("GOOGLE_SHEET_ID"))

    if sheets.is_paused():
        print("System is paused. Exiting.")
        return

    drive = DriveClient(config.load_service_account_json(), config.require_env("GOOGLE_DRIVE_FOLDER_ID"))

    due_for_cleanup = sheets.get_published_for_cleanup()
    if not due_for_cleanup:
        print("Nothing to clean up right now.")
        return

    cleaned = 0
    for row_index, row in due_for_cleanup:
        try:
            drive.delete_file(row["drive_file_id"])
            sheets.update_row_field(config.DAILY_LOG_TAB, row_index, "status", config.STATUS_CLEANED)
            sheets.update_row_field(config.DAILY_LOG_TAB, row_index, "cleaned_at", datetime.utcnow().isoformat())
            cleaned += 1
        except Exception as e:
            notifier.alert_critical(
                f"فشل حذف ملف من Drive: {row.get('topic_slug', 'unknown')}",
                str(e),
            )

    print(f"Cleaned up {cleaned} file(s).")


if __name__ == "__main__":
    main()
