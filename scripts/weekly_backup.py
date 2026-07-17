"""
Weekly backup — exports Daily_Log and Current_Plan as CSV and commits them
to /backups/ in the repo via the GitHub Contents API (no local git needed).
"""
import base64
import os
import sys
import time  # تم إضافة مكتبة الوقت لقياس الأداء
from datetime import datetime

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib import config
from lib.sheets_client import SheetsClient
from lib.telegram_notifier import TelegramNotifier

REQUIRED_VARS = [
    "GOOGLE_SHEET_ID",
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

    resp = requests.put(f"{api_base}/contents/{path}", headers=headers, json=body, timeout=20)
    if resp.status_code not in (200, 201):
        raise Exception(f"GitHub API Error: {resp.status_code} - {resp.text}")


def main():
    script_start_time = time.time()  # عداد الوقت الإجمالي
    print("🔄 جاري بدء سكربت النسخ الاحتياطي الأسبوعي وتدقيق المتغيرات...")
    config.check_required_env_vars(REQUIRED_VARS)

    notifier = TelegramNotifier(config.require_env("TELEGRAM_BOT_TOKEN"), config.require_env("TELEGRAM_CHAT_ID"))
    
    print("⏳ جاري الاتصال بـ Google Sheets Service...")
    sheets = SheetsClient(config.load_sheets_service_account_json(), config.require_env("GOOGLE_SHEET_ID"))

    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    github_pat = config.require_env("GH_PAT")
    github_repo = config.require_env("GH_REPO")

    try:
        tabs_to_backup = (config.DAILY_LOG_TAB, config.CURRENT_PLAN_TAB)
        
        for idx, tab in enumerate(tabs_to_backup, start=1):
            print(f"{idx}/3 — جاري تصدير ورقة العمل '{tab}' إلى CSV ورفعها إلى GitHub...")
            step_start = time.time()
            
            # تصدير البيانات من جوجل شيتس
            csv_content = sheets.export_tab_csv(tab)
            path = f"backups/{tab}_{date_str}.csv"
            
            # الالتزام بالرفع إلى مستودع الجيت هاب
            commit_file_to_github(github_pat, github_repo, path, csv_content, f"Weekly backup: {tab} {date_str}")
            
            print(f"    ✓ تم نسخ '{tab}' بنجاح (الوقت المنقضي: {time.time() - step_start:.2f} ثانية)")

        print("3/3 — جاري إرسال إشعار النجاح إلى تليجرام...")
        step_start = time.time()
        notifier.notify_success(f"تم النسخ الاحتياطي الأسبوعي بنجاح ({date_str})")
        print(f"    ✓ تم إرسال التنبيه (الوقت المنقضي: {time.time() - step_start:.2f} ثانية)")

        total_time = time.time() - script_start_time
        print(f"\n🎉 تم الانتهاء! الوقت الإجمالي للنسخ الاحتياطي: {total_time:.2f} ثانية.")

    except Exception as e:
        print(f"🔴 خطأ فادح أثناء التنفيذ: {str(e)}")
        notifier.alert_critical("فشل النسخ الاحتياطي الأسبوعي", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
