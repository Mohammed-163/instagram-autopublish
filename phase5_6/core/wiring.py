"""Run the weekly performance review and activate a new plan."""
from __future__ import annotations
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.container import container
from lib import config
from lib.telegram_notifier import TelegramNotifier


def main() -> int:
    notifier = TelegramNotifier(config.require_env("TELEGRAM_BOT_TOKEN"),
                                config.require_env("TELEGRAM_CHAT_ID"))
    try:
        wire_default_subscribers()
        container.resolve("weekly_performance_review_engine").run_weekly_review()
        notifier.notify_success("تمت مراجعة الأداء الأسبوعية وتفعيل الخطة الجديدة")
        return 0
    except Exception as exc:
        notifier.alert_critical("خطأ في مراجعة الأداء الأسبوعية", str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
