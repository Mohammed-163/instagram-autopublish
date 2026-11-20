"""Back up the plan, post log and configured databases to an owner-only Drive folder."""
from pathlib import Path
from tempfile import TemporaryDirectory

from operational.backup import _now_tag, backup_databases
from phase5_6.lib import config
from phase5_6.lib.drive_client import DriveClient
from phase5_6.lib.sheets_client import SheetsClient


def main():
    sheets = SheetsClient(config.load_sheets_service_account_json(), config.require_env("GOOGLE_SHEET_ID"))
    drive = DriveClient(config.load_drive_oauth_token_json(), "root")
    folder_id = drive.get_or_create_month_folder("instagram-autopublish-private-backups")
    tag = _now_tag()
    with TemporaryDirectory(prefix="instagram-backup-") as directory:
        target = Path(directory)
        for tab in (config.DAILY_LOG_TAB, config.CURRENT_PLAN_TAB):
            path = target / f"{tab}_{tag}.csv"
            path.write_text(sheets.export_tab_csv(tab), encoding="utf-8")
            drive.upload_private_backup(path, folder_id, "text/csv")
        databases = backup_databases(tag, directory=target)
        for path in databases:
            drive.upload_private_backup(Path(path), folder_id, "application/gzip")
    print(f"Private Drive backup complete: 2 CSV exports and {len(databases)} database backups.")


if __name__ == "__main__":
    main()
