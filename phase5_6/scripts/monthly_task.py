"""
Monthly task — runs on the 1st of each month:
1. Read the Post_Performance sheet (filled in daily by fetch_insights.py,
   3 days after each post publishes) + competitor.json from Manus
2. Send both to Gemini to build a 30-day plan, weighted toward whatever
   topics/angles actually performed best with the real audience
3. Archive Current_Plan -> Plan_History, write the new plan
4. Telegram summary of the new plan

NOTE: Meta token renewal used to be step 1 of this script. It now lives in
its own script (scripts/refresh_token.py) on a weekly schedule, so a
failure anywhere in this heavier 4-step job (Gemini quota, Sheets hiccup,
etc.) can never delay the token refresh and risk the token expiring.
"""
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib import config
from lib.error_handler import CriticalError
from lib.gemini_client import GeminiClient
from lib.drive_client import DriveClient
from lib.sheets_client import SheetsClient
from lib.telegram_notifier import TelegramNotifier

REQUIRED_VARS = [
    "GOOGLE_SHEET_ID", "GOOGLE_DRIVE_FOLDER_ID",
    "GEMINI_API_KEY_1",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
]


def main():
    script_start_time = time.time()  # عداد الوقت الإجمالي للسكربت
    config.check_required_env_vars(REQUIRED_VARS)

    notifier = TelegramNotifier(config.require_env("TELEGRAM_BOT_TOKEN"), config.require_env("TELEGRAM_CHAT_ID"))
    sheets = SheetsClient(config.load_sheets_service_account_json(), config.require_env("GOOGLE_SHEET_ID"))

    if sheets.is_paused():
        print("System is paused. Exiting.")
        return

    now = datetime.utcnow()
    month_label = now.strftime("%Y-%m")
    date_str = now.strftime("%Y-%m-%d")  # حساب تاريخ اليوم الحالي لتمريره لـ Gemini

    try:
        drive = DriveClient(config.load_drive_oauth_token_json(), config.require_env("GOOGLE_DRIVE_FOLDER_ID"))
        month_folder_id = drive.get_or_create_month_folder(month_label)

        # 1. Pull real post performance (built daily by fetch_insights.py,
        # 3 days after each post publishes) instead of generic last-30-days
        # media stats with no topic linkage.
        print("1/5 — Reading Post_Performance sheet...")
        step_start = time.time()
        performance_rows = sheets.get_all_post_performance()
        print(f"    ✓ Loaded {len(performance_rows)} performance row(s) (الوقت المنقضي: {time.time() - step_start:.2f} ثانية)")

        # 2. Competitor analysis (manual — Manus)
        print("2/5 — Looking for Manus's competitor.json in this month's Drive folder...")
        competitor_data = drive.download_json("competitor.json", month_folder_id)
        if competitor_data:
            print("    ✓ Found and loaded competitor.json")
        else:
            competitor_data = {}
            print("    ⚠ competitor.json not found yet — building the plan without it. "
                  "See MANUS_INSTRUCTIONS.md; rerun this task manually after Manus uploads it "
                  "if you want the plan to reflect competitor analysis.")

        # 3. Build plan
        print("3/5 — Building 30-day plan via Gemini...")
        step_start = time.time()
        gemini_keys = [config.optional_env("GEMINI_API_KEY_1"), config.optional_env("GEMINI_API_KEY_2"), config.optional_env("GEMINI_API_KEY_3")]
        gemini = GeminiClient(gemini_keys)
        plan_rows = gemini.build_monthly_plan({"posts": performance_rows}, competitor_data, date_str)
        print(f"    ✓ 30-day plan generated successfully (الوقت المنقضي: {time.time() - step_start:.2f} ثانية)")

        # 4. Archive + write new plan
        print("4/5 — Archiving old plan and writing new one...")
        step_start = time.time()
        sheets.archive_and_reset_plan(plan_rows, month_label)
        print(f"    ✓ Sheets updated successfully (الوقت المنقضي: {time.time() - step_start:.2f} ثانية)")

        # 5. Telegram summary
        print("5/5 — Sending summary and finishing up...")
        step_start = time.time()
        summary_lines = [f"{r[0]}: {r[1]} منشور" for r in plan_rows]
        notifier.notify_success(
            "تم إنشاء خطة الشهر بنجاح\n" + "\n".join(summary_lines[:10]) +
            (f"\n... و{len(summary_lines) - 10} يوماً إضافياً" if len(summary_lines) > 10 else "")
        )
        print(f"    ✓ Summary sent (الوقت المنقضي: {time.time() - step_start:.2f} ثانية)")
        
        total_time = time.time() - script_start_time
        print(f"\n🎉 Done. الإجمالي المستغرق للمهمة الشهرية بالكامل: {total_time:.2f} ثانية ({total_time/60:.2f} دقيقة).")

    except CriticalError as e:
        notifier.alert_critical("فشل المهمة الشهرية", str(e))
        sys.exit(1)
    except Exception as e:
        notifier.alert_critical("خطأ غير متوقع بالمهمة الشهرية", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
