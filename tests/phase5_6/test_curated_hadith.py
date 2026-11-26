from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from phase5_6.lib.curated_hadith import HADITH, HADITH_DAY, HADITH_STYLE, selected_curated_hadith
from phase5_6.scripts import daily_generate
from phase5_6.lib.video_creator import VideoCreator


def test_selection_is_explicit_one_slot_and_one_day():
    assert selected_curated_hadith(HADITH_DAY, 1, None) is None
    assert selected_curated_hadith(HADITH_DAY, 1, "false") is None
    assert selected_curated_hadith(HADITH_DAY, 1, "true") is HADITH
    assert selected_curated_hadith(HADITH_DAY, 2, "true") is None
    assert selected_curated_hadith(HADITH_DAY - timedelta(days=1), 1, "true") is None
    assert selected_curated_hadith(HADITH_DAY + timedelta(days=1), 1, "true") is None
    caption = HADITH.editorial_content()["caption_arabic"]
    assert caption.count(HADITH.quote) == 1
    assert caption.count(HADITH.source_url) == 1
    assert "باب من أبطأت عليه الإجابة" in caption
    assert "﴿" not in caption
    assert "سورة" not in caption


@pytest.fixture
def editor(monkeypatch):
    monkeypatch.setenv("CURATED_HADITH_ENABLED", "true")
    monkeypatch.delenv("DRY_RUN", raising=False)
    monkeypatch.setattr("sys.argv", ["daily_generate"])
    monkeypatch.setattr(daily_generate, "_check_required_env_vars", Mock())
    monkeypatch.setattr(daily_generate, "_require_env", Mock(return_value="test"))
    monkeypatch.setattr(daily_generate, "_load_json_secret", Mock(return_value="test"))
    monkeypatch.setattr(daily_generate, "TelegramNotifier", Mock())
    monkeypatch.setattr(daily_generate, "PixabayClient", Mock())
    monkeypatch.setattr(daily_generate, "_fetch_vetted_background", Mock(return_value="bg.png"))
    monkeypatch.setattr(daily_generate, "_get_today_theme_from_weekly_plan", Mock(return_value=(None, None)))
    monkeypatch.setattr(daily_generate, "today_baghdad", Mock(return_value=datetime(2026, 12, 1, 5)))
    history = {"post_indexes": set(), "explanations": [], "ayah_keys": set()}
    sheets = Mock()
    sheets.is_paused.return_value = False
    sheets.get_today_plan.return_value = {
        "post_count": 2, "post_1_time": "13:00", "post_1_topic": "دعاء", "post_1_ayah_key": "2:45",
        "post_2_time": "18:00", "post_2_topic": "شكراً", "post_2_ayah_key": "2:152",
    }
    sheets.get_weekly_content_history.return_value = history
    monkeypatch.setattr(daily_generate, "SheetsClient", Mock(return_value=sheets))
    renderer = Mock()
    renderer.build_post_video.side_effect = [("hadith.mp4", ""), ("quran.mp4", "approved.mp3")]
    monkeypatch.setattr(daily_generate, "VideoCreator", Mock(return_value=renderer))
    model = Mock()
    model.generate_hope_post_content.return_value = {
        "topic_slug": "quran-test", "hook_line": "كلام ثاني هادي اليوم وظريف",
        "iraqi_explanation": "وقفة ثانية مختلفة عن نص الحديث",
        "cta_line": "تابع للمزيد", "pixabay_query": "soft dusk sky",
        "caption_arabic": "كلام هادي", "hashtags": "#وقفة",
    }
    model.rewrite_situation_hook.return_value = "شي مختلف ثاني هادي اليوم"
    monkeypatch.setattr(daily_generate, "GeminiClient", Mock(return_value=model))
    drive = Mock()
    drive.upload_video.side_effect = ["hadith-test-id", "quran-test-id"]
    monkeypatch.setattr(daily_generate, "DriveClient", Mock(return_value=drive))
    return sheets, model, renderer, drive, history


def test_replaces_existing_slot_and_does_not_duplicate_on_rerun(editor):
    sheets, model, renderer, drive, history = editor
    daily_generate.main()
    rows = [call.args[0] for call in sheets.append_daily_log.call_args_list]
    assert len(rows) == 2
    hadith, quran = rows
    assert hadith["post_index"] == 1 and hadith["scheduled_time"] == "2026-12-01T10:00:00"
    assert quran["post_index"] == 2 and quran["scheduled_time"] == "2026-12-01T15:00:00"
    assert hadith["visual_style"] == HADITH_STYLE and not hadith["music_file"]
    assert not hadith["ayah_key"] and not hadith["ayah_text"]
    assert HADITH.source_url in hadith["caption_arabic"]
    assert quran["ayah_key"] == "2:152" and quran["music_file"] == "approved.mp3"
    assert quran["visual_style"].startswith("warm_stock_photo_quranic_frame__opener_")
    assert model.generate_hope_post_content.call_count == 1
    assert renderer.build_post_video.call_args_list[0].args[2] == HADITH.video_reference
    assert renderer.build_post_video.call_args_list[0].kwargs["hadith"] is True
    assert renderer.build_post_video.call_args_list[1].kwargs["hadith"] is False
    renderer.choose_music.assert_not_called()
    assert drive.upload_video.call_count == 2
    assert history["ayah_keys"] == {"2:152"}
    daily_generate.main()
    assert sheets.append_daily_log.call_count == 2
    assert drive.upload_video.call_count == 2


def test_workflow_dry_run_env_uploads_and_logs_nothing(editor, monkeypatch):
    sheets, model, renderer, drive, history = editor
    monkeypatch.setenv("DRY_RUN", "true")
    daily_generate.main()
    sheets.append_daily_log.assert_not_called()
    renderer.build_post_video.assert_not_called()
    drive.upload_video.assert_not_called()
    model.generate_hope_post_content.assert_not_called()


def test_renderer_silent_flag_bypasses_music(monkeypatch, tmp_path):
    renderer = object.__new__(VideoCreator)
    renderer.choose_music = Mock(side_effect=AssertionError("music should not be selected"))
    renderer.create_image = Mock()
    renderer.image_to_video = Mock()
    path, music_file = renderer.build_post_video(
        "synthetic-bg.png", HADITH.quote, HADITH.short_reference, HADITH.reflection,
        str(tmp_path), "silent.mp4", hook_line=HADITH.hook, hadith=True,
    )
    assert path.endswith("silent.mp4")
    assert music_file == ""
    assert renderer.create_image.call_args.kwargs["hadith"] is True
    assert renderer.image_to_video.call_args.args[-1] is None
