from collections import Counter
from datetime import date
from types import SimpleNamespace

from phase5_6.lib.audience_strategy import IDEAS, recommend
from phase5_6.scripts import monthly_task

WEEK = date(2026, 11, 29)
KEYS = {i.ayah_key for i in IDEAS}


def post(i, topic, saves=10, shares=5, **extra):
    return {
        "media_id": str(i), "topic": topic, "measured_24h": True,
        "reach": 1000, "saved": saves, "shares": shares,
        "published_at": "2026-11-23T13:00:00+00:00",
        "captured_at": "2026-11-24T13:15:00+00:00", **extra,
    }


def test_repeated_signal_wins_but_not_a_single_viral_reel():
    rows = [post(i, "power-of-dua", 20, 12) for i in range(3)]
    rows += [post(3, "relief-after-distress", 300, 300)] + [
        post(i, "relief-is-near", 0, 0) for i in range(4, 7)
    ]
    rows += [post(i, "unclassified", 10, 5) for i in range(7, 9)]
    result = recommend(rows, WEEK, KEYS)
    evidence = [i for i in result["ideas"] if i["mode"] == "evidence"]
    assert {i["theme"] for i in evidence} == {"دعاء"}
    assert evidence[0]["reason"] == {
        "posts": 3, "above_baseline": 3, "combined": 32,
        "saves": 20, "shares": 12, "eligible": True,
    }
    assert len(result["ideas"]) == 10
    assert max(Counter(i["theme"] for i in result["ideas"]).values()) == 2


def test_allows_verified_zero_but_excludes_missing_duplicate_small_late_and_future():
    rows = [post(1, "power-of-dua", 0, 0), post(1, "power-of-dua"),
            post(2, "power-of-dua", shares=None), post(3, "power-of-dua", reach=99),
            post(4, "power-of-dua", captured_at="2026-11-24T13:31:00+00:00"),
            post(5, "power-of-dua", published_at="2026-11-28T19:00:00Z", captured_at="2026-11-29T19:00:00Z"),
            post(6, "power-of-dua", raw_visual_style="base__opener_situation_fallback_v1"),
            post(7, "power-of-dua", measured_24h=False), post(8, "power-of-dua", saves=-1)]
    result = recommend(rows, WEEK, KEYS)
    assert result["sample_size"] == 1 and result["baseline"] == 0
    assert all(i["mode"] == "exploration" and i["reason"] is None for i in result["ideas"])


def test_candidate_verses_resolve_and_exploration_survives_without_data():
    real_keys = {v["key"] for v in monthly_task.load_verses()}
    assert KEYS <= real_keys and len(KEYS) == len(IDEAS)
    result = recommend([], WEEK, {"2:186"})
    assert [i["ayah_key"] for i in result["ideas"]] == ["2:186"]


def test_preview_entrypoint_does_not_invoke_sheets_model_or_notifications(monkeypatch, capsys):
    monkeypatch.setattr(monthly_task.sys, "argv", ["monthly_task", "--audience-preview"])
    monkeypatch.setattr(monthly_task, "load_supabase_performance_summary",
                        lambda **kw: {"_all_posts": []} if kw["include_editorial_metadata"] else {})
    def forbid(*args, **kwargs):
        raise AssertionError("preview used a publishing dependency")
    for name in ("SheetsClient", "GeminiClient", "TelegramNotifier"):
        monkeypatch.setattr(monthly_task, name, forbid)
    monthly_task.main()
    assert "Audience strategy (shadow):" in capsys.readouterr().out


def test_regular_strategy_unchanged_even_if_shadow_fails(monkeypatch, capsys):
    post_row = post(1, "power-of-dua", raw_visual_style="variant", score=1, views=1)
    monkeypatch.setattr(monthly_task.sys, "argv", ["monthly_task"])
    monkeypatch.setattr(monthly_task, "load_supabase_performance_summary",
                        lambda **kw: {"_all_posts": [post_row], "top_posts": [post_row], "sample_size": 1})
    monkeypatch.setattr(monthly_task.config, "check_required_env_vars", lambda *args: None)
    monkeypatch.setattr(monthly_task.config, "load_sheets_service_account_json", lambda: {})
    monkeypatch.setattr(monthly_task.config, "require_env", lambda *args: "test")
    monkeypatch.setattr(monthly_task.config, "optional_env", lambda *args: "")
    saved = []
    monkeypatch.setattr(monthly_task, "SheetsClient", lambda *args: SimpleNamespace(
        is_paused=lambda: False, archive_and_reset_plan=lambda rows, key: saved.append((rows, key))))
    monkeypatch.setattr(monthly_task, "TelegramNotifier",
                        lambda *args: SimpleNamespace(notify_success=lambda *args: None))
    def plan(performance, _week):
        assert "raw_visual_style" not in performance["top_posts"][0]
        assert "captured_at" not in performance["top_posts"][0]
        return {"posts": [{"topic": f"topic-{i}"} for i in range(10)]}
    monkeypatch.setattr(monthly_task, "GeminiClient", lambda *args: SimpleNamespace(build_weekly_content_plan=plan))
    def fail(*args):
        raise RuntimeError("must not log raw error message")
    monkeypatch.setattr(monthly_task, "audience_report", fail)
    monthly_task.main()
    assert [len(rows) for rows, _key in saved] == [7]
    assert "must not log" not in capsys.readouterr().out


def test_ordinary_shadow_log_contains_no_private_draft_or_metrics(capsys):
    report = monthly_task.audience_report([], WEEK)
    assert report["ideas"]
    output = capsys.readouterr().out
    assert output.strip() == "Audience strategy shadow preview checked; no production changes."
