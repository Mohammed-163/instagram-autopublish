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
from lib.gemini_client import GeminiClient, AllKeysExhaustedError, ImageVettingError
from lib.pixabay_client import PixabayClient
from lib.video_creator import VideoCreator
from lib.drive_client import DriveClient
from lib.sheets_client import SheetsClient
from lib.telegram_notifier import TelegramNotifier

REQUIRED_VARS = [
    "GOOGLE_SHEET_ID", "GOOGLE_DRIVE_FOLDER_ID",
    "GEMINI_API_KEY_1", "GEMINI_API_KEY_IMAGE_CHECK", "PIXABAY_API_KEY",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
]


def _fetch_vetted_background(pixabay, gemini, pixabay_query: str, topic_summary: str, tmpdir: str) -> str:
    """Downloads config.IMAGE_CANDIDATE_COUNT candidate images and asks
    Gemini (via the reserved image-check key) to reject any that aren't
    decent/halal and pick the best topical match among the rest. Falls back
    to the generic abstract query once if the first batch is fully rejected
    or unavailable. Raises if nothing usable is found either way.

    NOTE: select_best_image() returns the chosen item directly (a local file
    path string, or None) — it does NOT return an integer index.  The old code
    incorrectly compared the returned path to -1 and used it as a list index,
    causing a TypeError at runtime.  The fix: capture the return value as
    `chosen` and check `is None` instead of `< 0`.
    """
    candidates = pixabay.download_candidates(pixabay_query, tmpdir, n=config.IMAGE_CANDIDATE_COUNT)
    chosen = gemini.select_best_image(candidates, topic_summary) if candidates else None

    if chosen is None:
        print("⚠️ No suitable image among primary candidates — trying fallback keywords once.")
        candidates = pixabay.download_candidates(
            config.PIXABAY_FALLBACK_KEYWORDS, tmpdir, n=config.IMAGE_CANDIDATE_COUNT,
            filename_prefix="bg_fallback",
        )
        chosen = gemini.select_best_image(candidates, topic_summary) if candidates else None

    if chosen is None:
        raise RuntimeError(
            f"No compliant/suitable background image found for '{pixabay_query}' "
            f"or the fallback query, even after Gemini vetting."
        )

    return chosen


def _fetch_vetted_video(
    pixabay, gemini, pixabay_query: str, topic_summary: str, tmpdir: str
) -> str | None:
    """Download, review, and return an original accepted Pixabay video."""
    try:
        candidates = pixabay.download_video_candidates(
            pixabay_query, tmpdir, n=config.IMAGE_CANDIDATE_COUNT,
        )
        if not candidates:
            return None

        review_copies = []
        for i, video_path in enumerate(candidates):
            review_path = os.path.join(tmpdir, f"review_{i}.mp4")
            try:
                pixabay.create_review_copy(video_path, review_path)
                review_copies.append(review_path)
            except Exception as e:
                print(f"⚠️ Failed to create review copy for {video_path}: {e}")
                continue

        if not review_copies:
            return None

        selected_review = gemini.select_best_video(review_copies, topic_summary)
        if selected_review is None:
            return None

        idx = review_copies.index(selected_review)
        return candidates[idx]
    except Exception as e:
        print(f"⚠️ Video pipeline failed, falling back to images: {e}")
        return None


def today_baghdad() -> datetime:
    return datetime.now(pytz.timezone(config.BAGHDAD_TZ))


def _get_today_theme_from_weekly_plan(now: datetime) -> tuple[str | None, str | None]:
    """Read today's theme from the active weekly plan, failing open safely."""
    try:
        from core.container import container

        planning_service = container.resolve("weekly_planning_service")
        active_plan = planning_service.get_active_plan()
        if active_plan is None:
            return None, None
        plan_data = active_plan.plan
        if not isinstance(plan_data, dict) or "days" not in plan_data:
            return None, None
        day_name = now.strftime("%A").lower()
        day_data = plan_data["days"].get(day_name)
        if not isinstance(day_data, dict):
            return None, None
        return day_data.get("day_theme"), day_data.get("visual_mood")
    except Exception as e:
        print(f"⚠️ Failed to read weekly plan theme, continuing without it: {e}")
        return None, None


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
        day_theme, visual_mood = _get_today_theme_from_weekly_plan(now)
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
        gemini = GeminiClient(gemini_keys, image_check_key=config.require_env("GEMINI_API_KEY_IMAGE_CHECK"))
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

                # ── Step 5: Generate core content ──────────────────────────
                content = gemini.generate_post_content(
                    recent_topics, day_theme=day_theme, visual_mood=visual_mood,
                )

                # ── Step 5b: Generate caption + hashtags ────────────────────
                # generate_post_content does NOT produce caption_arabic or
                # hashtags; those require a separate Gemini call.  Without this
                # step, content["caption_arabic"] at the log-append stage would
                # always raise KeyError.
                caption_data = gemini.generate_caption_and_hashtags(
                    content["hook_line"], content["fact_line"], content["cta_line"]
                )
                content.update(caption_data)

                # Normalise hashtags: generate_caption_and_hashtags returns a
                # space-separated string ("#tag1 #tag2 …").  The log-append
                # step does " ".join(list), so we convert to list here once.
                # Without this, " ".join(str) would join individual characters.
                raw_hashtags = content.get("hashtags", "")
                if isinstance(raw_hashtags, str):
                    content["hashtags"] = raw_hashtags.split()

                # ── Step 6/7: Validate ALL required fields ──────────────────
                # This gate must run before ANY media operation so that a bad
                # generation response is caught here with a clear message
                # rather than as a cryptic KeyError inside the media stage.
                _REQUIRED = [
                    "topic_slug", "hook_line", "fact_line", "cta_line",
                    "pixabay_query", "caption_arabic", "hashtags",
                ]
                _missing = [f for f in _REQUIRED if not content.get(f)]
                if _missing:
                    raise ValueError(
                        f"Content generation incomplete — missing required fields: {_missing}. "
                        f"Present keys: {list(content.keys())}"
                    )

                # ── Step 8: Search / download media ────────────────────────
                bg_file_id = (plan or {}).get(f"post_{i}_bg_file_id")
                with tempfile.TemporaryDirectory() as tmpdir:
                    bg_path = os.path.join(tmpdir, "bg.jpg")
                    is_video_background = False
                    if bg_file_id:
                        # Pre-selected asset from the monthly plan is assumed
                        # already vetted (manually placed) — download as-is.
                        drive.download_file(bg_file_id, bg_path)
                    else:
                        topic_summary = f"{content['hook_line']} — {content['fact_line']}"
                        final_pixabay_query = content["pixabay_query"]
                        if visual_mood:
                            final_pixabay_query = f"{content['pixabay_query']} {visual_mood}"
                        if config.PIXABAY_VIDEO_MODE:
                            video_path = _fetch_vetted_video(
                                pixabay, gemini, final_pixabay_query, topic_summary, tmpdir,
                            )
                            if video_path is not None:
                                bg_path = video_path
                                is_video_background = True
                            else:
                                print("⚠️ No acceptable video found, falling back to image path")
                                bg_path = _fetch_vetted_background(
                                    pixabay, gemini, final_pixabay_query, topic_summary, tmpdir,
                                )
                                is_video_background = False
                        else:
                            bg_path = _fetch_vetted_background(
                                pixabay, gemini, final_pixabay_query, topic_summary, tmpdir,
                            )
                            is_video_background = False

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
            except ImageVettingError as e:
                # Image vetting is a hard prerequisite: we must not publish
                # without a vetted background image.  Escalate to CriticalError
                # so the whole day's run stops immediately rather than silently
                # skipping the image-selection step.
                raise CriticalError(f"فشل فحص الصور عبر Gemini Vision: {e}")
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
