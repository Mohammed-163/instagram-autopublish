from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from phase5_6.scripts import fetch_insights, monthly_task, publish


def test_stale_publication_is_reported_without_ready_posts(monkeypatch):
    sheets, notifier, ig = MagicMock(), MagicMock(), MagicMock()
    sheets.is_paused.return_value = False
    sheets.get_ready_posts_due_now.return_value = []
    sheets.get_stale_publishing_rows.return_value = [(2, {"topic_slug": "stuck"})]
    monkeypatch.setattr(publish.config, "check_required_env_vars", lambda *_: None)
    monkeypatch.setattr(publish.config, "require_env", lambda *_: "test")
    monkeypatch.setattr(publish.config, "load_sheets_service_account_json", lambda: "{}")
    monkeypatch.setattr(publish, "TelegramNotifier", lambda *_: notifier)
    monkeypatch.setattr(publish, "SheetsClient", lambda *_: sheets)
    monkeypatch.setattr(publish, "InstagramClient", lambda *_: ig)
    publish.main()
    notifier.alert_critical.assert_called_once()
    ig.publish_container.assert_not_called()


def test_failed_final_publish_preserves_reservation(monkeypatch):
    sheets, notifier, ig, drive = (MagicMock() for _ in range(4))
    sheets.is_paused.return_value = False
    sheets.get_ready_posts_due_now.return_value = [(2, {"topic_slug": "test", "drive_file_id": "drive-id"})]
    ig.publish_container.side_effect = publish.InstagramAPIError("uncertain result")
    monkeypatch.setattr(publish.config, "check_required_env_vars", lambda *_: None)
    monkeypatch.setattr(publish.config, "require_env", lambda *_: "test")
    monkeypatch.setattr(publish.config, "load_sheets_service_account_json", lambda: "{}")
    monkeypatch.setattr(publish.config, "load_drive_oauth_token_json", lambda: "{}")
    monkeypatch.setattr(publish, "TelegramNotifier", lambda *_: notifier)
    monkeypatch.setattr(publish, "SheetsClient", lambda *_: sheets)
    monkeypatch.setattr(publish, "InstagramClient", lambda *_: ig)
    monkeypatch.setattr(publish, "DriveClient", lambda *_: drive)
    with pytest.raises(SystemExit):
        publish.main()
    assert sheets.update_row_fields.call_count == 1
    assert sheets.update_row_fields.call_args.args[2]["status"] == publish.config.STATUS_PUBLISHING


def test_weekly_learning_excludes_late_snapshots(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'measurements.db'}"
    monkeypatch.setenv("ALLOW_SQLITE_FALLBACK", "true")
    monkeypatch.setenv("LEARNING_LAYER_DATABASE_URL", url)
    engine = create_engine(url)
    fetch_insights.ensure_snapshot_table(engine)
    published = datetime.now(timezone.utc) - timedelta(days=7)
    target = published + timedelta(days=1)
    with Session(engine) as session, session.begin():
        for media_id, delay in (("on-time", 15), ("late", 31), ("early", -1)):
            result = fetch_insights._save_snapshot(
                session, {"media_id": media_id, "published_at": published.isoformat()},
                "24h", target, target + timedelta(minutes=delay), {"reach": 100, "views": 150},
            )
            assert result
    performance = monthly_task.load_supabase_performance_summary()
    assert performance["sample_size"] == 1
    assert performance["top_posts"][0]["media_id"] == "on-time"
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM instagram_insight_snapshots")).scalar_one() == 3
    engine.dispose()


def test_snapshot_rolls_back_when_learning_write_fails():
    engine = create_engine("sqlite://")
    fetch_insights.ensure_snapshot_table(engine)
    now = datetime.now(timezone.utc)
    row = {"media_id": "atomic-post", "published_at": now.isoformat()}
    with pytest.raises(RuntimeError, match="learning failed"):
        with Session(engine) as session, session.begin():
            assert fetch_insights._save_snapshot(session, row, "1h", now, now, {"reach": 100})
            raise RuntimeError("learning failed")
    assert fetch_insights._read_snapshots(engine, "atomic-post") == set()
    engine.dispose()


def test_posting_hours_use_median_views_with_minimum_samples():
    week_start = datetime(2026, 11, 22, tzinfo=timezone.utc)
    posts = []
    for utc_hour, views in ((10, [2000, 2100, 2200]), (15, [600, 650, 50000]), (17, [10000])):
        published = (week_start - timedelta(days=3)).replace(hour=utc_hour)
        posts.extend(
            {"published_at": published.isoformat(), "views": count, "reach": 100,
             "score": 0.1, "measured_24h": True}
            for count in views
        )
    policy = monthly_task.choose_publishing_times(posts, week_start.date())
    assert policy["single"] == "13:00"
    assert policy["double"] == ["13:00", "18:00"]
    assert policy["hour_stats"][18]["median_views"] == 650
