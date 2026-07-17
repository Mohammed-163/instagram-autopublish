"""
Daily generation workflow — runs at 05:00 Baghdad time.
Reads today's plan, generates N posts (content + video), uploads to Drive,
logs to Daily_Log with status=ready.
"""
import argparse
import os
import sys
import tempfile
from datetime import datetime

import pytz

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib import config
from lib.error_handler import handle_unexpected, CriticalError, RecoverableError
from lib.gemini_client import GeminiClient, AllKeysExhaustedError
from lib.pixabay_client import PixabayClient
from lib.video_creator import VideoCreator
from lib.drive_client import DriveClient
from lib.sheets_client import SheetsClient
from lib.telegram_notifier import TelegramNotifier

REQUIRED_VARS = [
    "GOOGLE_SHEET_ID", "GOOGLE_DRIVE_FOLDER_ID",
    "GEMINI_API_KEY_1", "PIXABAY_API_KEY",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
]


def today_baghdad() -> datetime:
    return datetime.now(pytz.timezone(config.BAGHDAD_TZ))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config.check_required_env_vars(REQUIRED_VARS)

    notifier = TelegramNotifier(config.require_env("TELEGRAM_BOT_TOKEN"), config.require_env("TELEGRAM_CHAT_ID"))
    sheets = SheetsClient(config.load_sheets_service_account_json(), config.require_env("GOOGLE_SHEET_ID"))

    try:
        if sheets.is_paused():
            print("System is paused (system_status=paused). Exiting.")
            return

        now = today_baghdad()
        date_str = now.strftime("%Y-%m-%d")
        month_label = now.strftime("%Y-%m")

        plan = sheets.get_today_plan(date_str)
        if plan:
            post_count = int(plan.get("post_count", 1))
        else:
            post_count = 1  # fallback: one free-topic post if no plan row exists

        gemini_keys = [
            config.optional_env("GEMINI_API_KEY_1"),
            config.optional_env("GEMINI_API_KEY_2"),
            config.optional_env("GEMINI_API_KEY_3"),
        ]
        gemini = GeminiClient(gemini_keys)
        pixabay = PixabayClient(config.require_env("PIXABAY_API_KEY"))
        video_creator = VideoCreator()

        if args.dry_run:
            print(f"[DRY RUN] Would generate {post_count} post(s) for {date_str}")
            return

        drive = DriveClient(config.load_drive_oauth_token_json(), config.require_env("GOOGLE_DRIVE_FOLDER_ID"))
        month_folder_id = drive.get_or_create_month_folder(month_label)

        generated = 0
        for i in range(1, post_count + 1):
            try:
                recent_topics = sheets.get_recent_topics()
                content = gemini.generate_post_content(recent_topics)

                bg_file_id = plan.get(f"post_{i}_bg_file_id") if plan else None
                with tempfile.TemporaryDirectory() as tmpdir:
                    bg_path = os.path.join(tmpdir, "bg.jpg")
                    if bg_file_id:
                        drive.download_file(bg_file_id, bg_path)
                    else:
                        pixabay.download_background(content["pixabay_query"], bg_path)

                    video_path = video_creator.build_post_video(
                        bg_path, content["hook_line"], content["fact_line"], content["cta_line"],
                        tmpdir, f"post_{date_str}_{i}.mp4",
                    )

                    drive_file_id = drive.upload_video(video_path, os.path.basename(video_path), month_folder_id)
                    drive.make_public(drive_file_id)

                scheduled_time_hhmm = (plan.get(f"post_{i}_time") if plan else None) or now.strftime("%H:%M")
                # post_N_time from the monthly plan is Baghdad-local (best audience
                # engagement hours). Everything else in Daily_Log (published_at,
                # cleaned_at) is stored in UTC via datetime.utcnow(), and publish.py
                # compares scheduled_time against UTC — so convert here to keep the
                # whole sheet on one consistent clock.
                baghdad_tz = pytz.timezone(config.BAGHDAD_TZ)
                naive_local = datetime.strptime(f"{date_str} {scheduled_time_hhmm}", "%Y-%m-%d %H:%M")
                scheduled_dt_utc = baghdad_tz.localize(naive_local).astimezone(pytz.utc)
                scheduled_time_iso = scheduled_dt_utc.strftime("%Y-%m-%dT%H:%M:%S")

                sheets.append_daily_log({
                    "date": date_str,
                    "post_index": i,
                    "topic_slug": content["topic_slug"],
                    "hook_line": content["hook_line"],
                    "fact_line": content["fact_line"],
                    "cta_line": content["cta_line"],
                    "caption_arabic": content["caption_arabic"],
                    "hashtags": " ".join(content.get("hashtags", [])),
                    "background_query": content.get("pixabay_query", ""),
                    "drive_file_id": drive_file_id,
                    "scheduled_time": scheduled_time_iso,
                    "status": config.STATUS_READY,
                    "published_at": "",
                    "cleaned_at": "",
                })
                generated += 1

            except AllKeysExhaustedError as e:
                raise CriticalError(f"كل مفاتيح Gemini استُنفدت: {e}")
            except Exception:
                handle_unexpected(
                    notifier, gemini,
                    config.optional_env("GH_PAT"), config.optional_env("GH_REPO"),
                    "scripts/daily_generate.py", "post generation loop iteration", date_str,
                )
                continue  # try the next post rather than aborting the whole day

        notifier.notify_success(f"تم توليد {generated}/{post_count} منشور ليوم {date_str}")

    except CriticalError as e:
        notifier.alert_critical("فشل التوليد اليومي", str(e))
        sys.exit(1)
    except RecoverableError as e:
        print(f"Recoverable error, will retry next run: {e}")


if __name__ == "__main__":
    main()
