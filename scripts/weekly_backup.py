"""
Weekly backup — exports Daily_Log and Current_Plan as CSV and commits them
to /backups/ in the repo via the GitHub Contents API (no local git needed).
"""
import base64
import os
import sys
from datetime import datetime

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib import config
from lib.sheets_client import SheetsClient
from lib.telegram_notifier import TelegramNotifier

REQUIRED_VARS = [
    "GOOGLE_SERVICE_ACCOUNT_JSON", "GOOGLE_SHEET_ID",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
    "GH_PAT", "GH_REPO",
]


def commit_file_to_github(github_pat: str, github_repo: str, path: str, content: str, message: str) -> None:
    headers = {"Authorization": f"token {github_pat}", "Accept": "application/vnd.github+json"}
    api_base = f"https://api.github.com/repos/{github_repo}"

    existing = requests.get(f"{api_base}/contents/{path}", headers=headers, timeout=20)
    sha = existing.json().get("sha") if existing.status_code == 200 else None

    body = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
    }
    if sha:
        body["sha"] = sha

    requests.put(f"{api_base}/contents/{path}", headers=headers, json=body, timeout=20)


def main():
    config.check_required_env_vars(REQUIRED_VARS)

    notifier = TelegramNotifier(config.require_env("TELEGRAM_BOT_TOKEN"), config.require_env("TELEGRAM_CHAT_ID"))
    sheets = SheetsClient(config.require_env("GOOGLE_SERVICE_ACCOUNT_JSON"), config.require_env("GOOGLE_SHEET_ID"))

    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    github_pat = config.require_env("GH_PAT")
    github_repo = config.require_env("GH_REPO")

    try:
        for tab in (config.DAILY_LOG_TAB, config.CURRENT_PLAN_TAB):
            csv_content = sheets.export_tab_csv(tab)
            path = f"backups/{tab}_{date_str}.csv"
            commit_file_to_github(github_pat, github_repo, path, csv_content, f"Weekly backup: {tab} {date_str}")

        notifier.notify_success(f"تم النسخ الاحتياطي الأسبوعي بنجاح ({date_str})")
    except Exception as e:
        notifier.alert_critical("فشل النسخ الاحتياطي الأسبوعي", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
