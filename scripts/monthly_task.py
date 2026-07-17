"""
Monthly task — runs on the 1st of each month:
1. Renew the Meta long-lived token, verify it, update the GitHub secret
2. Pull last-30-days insights for all recent media -> JSON to Drive
3. (Manus runs competitor analysis manually per MANUS_INSTRUCTIONS.md,
   uploading its output JSON to the same Drive folder)
4. Send both JSON files to Gemini to build a 30-day plan
5. Archive Current_Plan -> Plan_History, write the new plan
6. (Skipped) Pre-download backgrounds is removed to conserve Gemini quota
7. Telegram summary of the new plan
"""
import base64
import os
import sys
import time  # تم إضافة مكتبة الوقت لقياس الأداء
from datetime import datetime

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib import config
from lib.error_handler import CriticalError
from lib.gemini_client import GeminiClient
from lib.instagram_client import InstagramClient, InstagramAPIError
from lib.drive_client import DriveClient
from lib.sheets_client import SheetsClient
from lib.telegram_notifier import TelegramNotifier

REQUIRED_VARS = [
    "GOOGLE_SHEET_ID", "GOOGLE_DRIVE_FOLDER_ID",
    "GEMINI_API_KEY_1", "PIXABAY_API_KEY",
    "IG_ACCESS_TOKEN", "IG_BUSINESS_ID", "FB_APP_ID", "FB_APP_SECRET",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
    "GH_PAT", "GH_REPO",
]


def update_github_secret(github_pat: str, github_repo: str, secret_name: str, secret_value: str) -> None:
    """Updates a repository secret via the GitHub API (libsodium-encrypted)."""
    from nacl import encoding, public

    headers = {"Authorization": f"token {github_pat}", "Accept": "application/vnd.github+json"}
    api_base = f"https://api.github.com/repos/{github_repo}"

    key_resp = requests.get(f"{api_base}/actions/secrets/public-key", headers=headers, timeout=20).json()
    public_key = public.PublicKey(key_resp["key"].encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    encrypted_b64 = base64.b64encode(encrypted).decode("utf-8")

    requests.put(
        f"{api_base}/actions/secrets/{secret_name}", headers=headers, timeout=20,
        json={"encrypted_value": encrypted_b64, "key_id": key_resp["key_id"]},
    )


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
        # 1. Token renewal
        print("1/7 — Renewing Meta access token...")
        step_start = time.time()
        new_token = InstagramClient.exchange_token(
            config.require_env("FB_APP_ID"), config.require_env("FB_APP_SECRET"), config.require_env("IG_ACCESS_TOKEN"),
        )
        ig = InstagramClient(new_token, config.require_env("IG_BUSINESS_ID"))
        if not ig.verify_token():
            raise CriticalError("التوكن الجديد بعد التجديد لم يجتز التحقق")
        update_github_secret(config.require_env("GH_PAT"), config.require_env("GH_REPO"), "IG_ACCESS_TOKEN", new_token)
        print(f"    ✓ Token renewed and secret updated (الوقت المنقضي: {time.time() - step_start:.2f} ثانية)")

        drive = DriveClient(config.load_drive_oauth_token_json(), config.require_env("GOOGLE_DRIVE_FOLDER_ID"))
        month_folder_id = drive.get_or_create_month_folder(month_label)

        # 2. Pull insights
        print("2/7 — Pulling last 30 days of insights...")
        step_start = time.time()
        recent_media = ig.get_recent_media(limit=30)
        insights_data = []
        for m in recent_media:
            try:
                metrics = ig.get_media_insights(m["id"])
                insights_data.append({**m, **metrics})
            except InstagramAPIError:
                continue
        drive.upload_json({"month": month_label, "media": insights_data}, "insights.json", month_folder_id)
        print(f"    ✓ Pulled insights for {len(insights_data)} posts (الوقت المنقضي: {time.time() - step_start:.2f} ثانية)")

        # 3. Competitor analysis (manual — Manus)
        print("3/7 — Looking for Manus's competitor.json in this month's Drive folder...")
        competitor_data = drive.download_json("competitor.json", month_folder_id)
        if competitor_data:
            print("    ✓ Found and loaded competitor.json")
        else:
            competitor_data = {}
            print("    ⚠ competitor.json not found yet — building the plan without it. "
                  "See MANUS_INSTRUCTIONS.md; rerun this task manually after Manus uploads it "
                  "if you want the plan to reflect competitor analysis.")

        # 4. Build plan
        print("4/7 — Building 30-day plan via Gemini...")
        step_start = time.time()
        gemini_keys = [config.optional_env("GEMINI_API_KEY_1"), config.optional_env("GEMINI_API_KEY_2"), config.optional_env("GEMINI_API_KEY_3")]
        gemini = GeminiClient(gemini_keys)
        # تم تعديل السطر التالي لتمرير متغير التاريخ الحالي date_str كمعامل ثالث
        plan_rows = gemini.build_monthly_plan({"media": insights_data}, competitor_data, date_str)
        print(f"    ✓ 30-day plan generated successfully (الوقت المنقضي: {time.time() - step_start:.2f} ثانية)")

        # 5. Archive + write new plan
        print("5/7 — Archiving old plan and writing new one...")
        step_start = time.time()
        sheets.archive_and_reset_plan(plan_rows, month_label)
        print(f"    ✓ Sheets updated successfully (الوقت المنقضي: {time.time() - step_start:.2f} ثانية)")

        # 6. Pre-download backgrounds
        print("6/7 — Skipping pre-download (Backgrounds will be fetched dynamically daily)...")

        # 7. Telegram summary
        print("7/7 — Sending summary and finishing up...")
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
