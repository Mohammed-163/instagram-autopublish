"""
Cleanup — runs at midnight Baghdad time. Deletes Drive videos for posts
published before the cleanup run (status-based, not a blind fixed-time delete).
"""
import os
import sys
from datetime import datetime

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib import config
from lib.drive_client import DriveClient
from lib.error_handler import handle_unexpected
from lib.sheets_client import SheetsClient
from lib.telegram_notifier import TelegramNotifier

REQUIRED_VARS = [
    "GOOGLE_SHEET_ID", "GOOGLE_DRIVE_FOLDER_ID",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
]


def main():
    config.check_required_env_vars(REQUIRED_VARS)

    notifier = TelegramNotifier(config.require_env("TELEGRAM_BOT_TOKEN"), config.require_env("TELEGRAM_CHAT_ID"))
    sheets = SheetsClient(config.load_sheets_service_account_json(), config.require_env("GOOGLE_SHEET_ID"))

    if sheets.is_paused():
        print("System is paused. Exiting.")
        return

    drive = DriveClient(config.load_drive_oauth_token_json(), config.require_env("GOOGLE_DRIVE_FOLDER_ID"))
    due_for_cleanup = sheets.get_published_for_cleanup()
    if not due_for_cleanup:
        print("Nothing to clean up right now.")
        return

    cleaned = 0
    for row_index, row in due_for_cleanup:
        try:
            drive.delete_file(row["drive_file_id"])
            sheets.update_row_fields(
                config.DAILY_LOG_TAB, row_index,
                {"status": config.STATUS_CLEANED, "cleaned_at": datetime.utcnow().isoformat()},
                verify_field="topic_slug", verify_value=row.get("topic_slug"),
            )
            cleaned += 1
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            print(f"⚠️ Transient network error cleaning up {row.get('topic_slug')}, will retry next run: {e}")
        except Exception:
            handle_unexpected(notifier, "phase5_6/scripts/cleanup.py")

    print(f"Cleaned up {cleaned} file(s).")


if __name__ == "__main__":
    main()
