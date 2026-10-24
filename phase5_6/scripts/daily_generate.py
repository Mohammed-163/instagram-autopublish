"""
Daily generation workflow — runs at 05:00 Baghdad time.
Reads today's plan, generates N posts (content + video), uploads to Drive,
logs to Daily_Log with status=ready.
"""
import argparse
import json
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
from lib.quran_content import explanation_is_duplicate, sunday_of, verse_by_key

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
    """Download, review, and return an original accepted Pixabay video.
    Falls back to config.PIXABAY_FALLBACK_KEYWORDS once if the primary query
    yields no accepted candidate, mirroring _fetch_vetted_background's retry logic.
    """
    def _try_query(query: str, prefix: str) -> str | None:
        print(f"[DIAG] _try_query called with query='{query}' prefix='{prefix}'")
        try:
            candidates = pixabay.download_video_candidates(
                query, tmpdir, n=config.IMAGE_CANDIDATE_COUNT,
                filename_prefix=prefix,
            )
            if not candidates:
                return None

            review_copies = []
            for i, video_path in enumerate(candidates):
                review_path = os.path.join(tmpdir, f"{prefix}_review_{i}.mp4")
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
            print(f"⚠️ Video pipeline failed for query '{query}': {e}")
            return None

    result = _try_query(pixabay_query, "bg_video_candidate")
    if result is not None:
        return result

    print("⚠️ No suitable video among primary candidates — trying fallback keywords once.")
    return _try_query(config.PIXABAY_FALLBACK_KEYWORDS, "bg_video_fallback")


def today_baghdad() -> datetime:
    return datetime.now(pytz.timezone(config.BAGHDAD_TZ))


def _check_required_env_vars(names: list[str]) -> None:
    """Use config's validator when available, with a compatibility fallback."""
    validator = getattr(config, "check_required_env_vars", None)
    if callable(validator):
        validator(names)
        return
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}", file=sys.stderr)
        raise SystemExit(1)


def _require_env(name: str) -> str:
    getter = getattr(config, "require_env", None)
    if callable(getter):
        return getter(name)
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _optional_env(name: str, default: str = "") -> str:
    getter = getattr(config, "optional_env", None)
    if callable(getter):
        return getter(name, default)
    return os.environ.get(name, default)


def _load_json_secret(loader_name: str, encoded_name: str, raw_name: str) -> str:
    loader = getattr(config, loader_name, None)
    if callable(loader):
        return loader()
    encoded = os.environ.get(encoded_name)
    if encoded:
        import base64
        try:
            return base64.b64decode(encoded, validate=True).decode("utf-8")
        except Exception as exc:
            raise RuntimeError(f"Invalid {encoded_name}: {exc}") from exc
    return _require_env(raw_name)


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

    _check_required_env_vars(REQUIRED_VARS)

    notifier = TelegramNotifier(_require_env("TELEGRAM_BOT_TOKEN"), _require_env("TELEGRAM_CHAT_ID"))
    sheets = SheetsClient(
        _load_json_secret("load_sheets_service_account_json", "GOOGLE_SERVICE_ACCOUNT_JSON_B64", "GOOGLE_SERVICE_ACCOUNT_JSON"),
        _require_env("GOOGLE_SHEET_ID"),
    )

    try:
        if sheets.is_paused():
            print("System is paused (system_status=paused). Exiting.")
            return

        now = today_baghdad()
        day_theme, visual_mood = _get_today_theme_from_weekly_plan(now)
        date_str = now.strftime("%Y-%m-%d")
        month_label = now.strftime("%Y-%m")
        week_start = sunday_of(now.date()).isoformat()

        plan = sheets.get_today_plan(date_str)
        if not plan:
            raise CriticalError(f"لا توجد خطة أسبوعية لهذا اليوم ({date_str})؛ لن يتم إنشاء منشور خارج الخطة.")
        post_count = int(plan.get("post_count", 0) or 0)
        if post_count not in (1, 2):
            raise CriticalError(f"عدد منشورات الخطة غير صالح للتاريخ {date_str}: {post_count}")
        history = sheets.get_weekly_content_history(week_start)
        recent_explanations = list(history["explanations"])

        gemini_keys = [
            _optional_env("GEMINI_API_KEY_1"),
            _optional_env("GEMINI_API_KEY_2"),
            _optional_env("GEMINI_API_KEY_3"),
        ]
        gemini = GeminiClient(gemini_keys, image_check_key=_require_env("GEMINI_API_KEY_IMAGE_CHECK"))
        pixabay = PixabayClient(_require_env("PIXABAY_API_KEY"))
        video_creator = VideoCreator()

        if args.dry_run:
            print(f"[DRY RUN] Would generate {post_count} post(s) for {date_str} from weekly plan {week_start}")
            return

        drive = DriveClient(
            _load_json_secret("load_drive_oauth_token_json", "GOOGLE_OAUTH_TOKEN_JSON_B64", "GOOGLE_OAUTH_TOKEN_JSON"),
            _require_env("GOOGLE_DRIVE_FOLDER_ID"),
        )
        month_folder_id = drive.get_or_create_month_folder(month_label)
        try:
            video_creator.choose_music()  # fail before spending API calls when mp3/ is empty
        except FileNotFoundError as exc:
            raise CriticalError(str(exc)) from exc

        generated = 0
        for i in range(1, post_count + 1):
            try:
                if (date_str, i) in history["post_indexes"]:
                    print(f"✓ Post slot {date_str} #{i} already exists; skipping to prevent duplicate generation.")
                    continue
                recent_topics = sheets.get_recent_topics()
                planned_topic = str(plan.get(f"post_{i}_topic") or "").strip()
                verse_key = str(plan.get(f"post_{i}_ayah_key") or "").strip()
                if not planned_topic or not verse_key:
                    raise CriticalError(f"الخطة الأسبوعية لا تحتوي موضوعاً وآية للمنشور #{i} في {date_str}.")
                if verse_key in history["ayah_keys"]:
                    raise CriticalError(f"الآية {verse_key} مستخدمة مسبقاً هذا الأسبوع؛ أعد إنشاء الخطة الأسبوعية.")
                verse = verse_by_key(verse_key)

                content = gemini.generate_hope_post_content(
                    planned_topic,
                    verse["text"],
                    f"{verse['surah']} {verse['key']}",
                    recent_explanations,
                    learned_hook_guidance=str(plan.get(f"post_{i}_hook_guidance") or ""),
                )
                content["hook_line"] = content["hook_line"].strip()
                content["fact_line"] = content["iraqi_explanation"].strip()
                content["caption_arabic"] = (
                    f"{content['caption_arabic'].strip()}\n\n"
                    f"﴿{verse['text']}﴾\n({verse['surah']}، الآية {verse['ayah']})"
                )
                if explanation_is_duplicate(content["fact_line"], recent_explanations):
                    raise ValueError("تفسير الآية مكرر أو قريب جداً من شرح سابق في هذا الأسبوع؛ أعد المحاولة.")

                # Keep hashtags as tokens for the Daily_Log join below.
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

                # Download and vet a fresh free stock photograph for every post.
                with tempfile.TemporaryDirectory() as tmpdir:
                    bg_path = os.path.join(tmpdir, "bg.jpg")
                    topic_summary = f"{planned_topic} — {verse['text']} — {content['fact_line']}"
                    final_pixabay_query = content["pixabay_query"]
                    if visual_mood:
                        final_pixabay_query = f"{final_pixabay_query} {visual_mood}"
                    bg_path = _fetch_vetted_background(
                        pixabay, gemini, final_pixabay_query, topic_summary, tmpdir,
                    )

                    output_filename = f"post_{date_str}_{i}.mp4"
                    video_path, music_filename = video_creator.build_post_video(
                        bg_path, verse["text"], f"{verse['surah']}، الآية {verse['ayah']}",
                        content["fact_line"], tmpdir, output_filename,
                        hook_line=content["hook_line"],
                        music_weights=json.loads(plan.get("music_weights_json") or "{}"),
                    )

                    drive_file_id = drive.upload_video(
                        video_path,
                        os.path.basename(video_path),
                        month_folder_id,
                    )
                    drive.make_public(drive_file_id)

                # Enforce the current policy even when the weekly sheet still
                # contains previous 19:00/23:00 values.
                default_time = "13:00" if post_count == 2 and i == 1 else "18:00"
                scheduled_time_hhmm = str(plan.get(f"post_{i}_time") or default_time).strip()
                try:
                    datetime.strptime(scheduled_time_hhmm, "%H:%M")
                except ValueError as exc:
                    raise CriticalError(
                        f"Invalid planned time in Current_Plan for post_{i}_time: "
                        f"{scheduled_time_hhmm!r}; expected HH:MM Baghdad time."
                    ) from exc
                # post_N_time from the weekly plan is Baghdad-local (best audience
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
                    "ayah_key": verse["key"],
                    "ayah_text": verse["text"],
                    "iraqi_explanation": content["fact_line"],
                    "music_file": music_filename,
                    "visual_style": "warm_stock_photo_quranic_frame",
                    "drive_file_id": drive_file_id,
                    "scheduled_time": scheduled_time_iso,
                    "status": config.STATUS_READY,
                    "published_at": "",
                    "cleaned_at": "",
                })
                generated += 1
                history["ayah_keys"].add(verse["key"])
                history["explanations"].append(content["fact_line"])
                recent_explanations.append(content["fact_line"])
                history["post_indexes"].add((date_str, i))

            except CriticalError:
                raise
            except FileNotFoundError as e:
                raise CriticalError(str(e)) from e
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
                    _optional_env("GH_PAT"), _optional_env("GH_REPO"),
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
