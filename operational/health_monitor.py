"""
Health Monitor
==============
Tracks pipeline execution status, sends Telegram alerts,
and maintains a heartbeat file readable by health_check workflow.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger("operational.health_monitor")

BAGHDAD_OFFSET = timedelta(hours=3)
STATUS_FILE = os.environ.get(
    "HEALTH_STATUS_FILE",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "health_status.json"),
)


def _now_baghdad() -> str:
    return datetime.now(tz=timezone(BAGHDAD_OFFSET)).isoformat()


@dataclass
class PipelineStatus:
    name:           str
    last_run_at:    str  = ""
    last_status:    str  = "pending"   # pending | running | success | failure | skipped
    last_error:     str  = ""
    run_count:      int  = 0
    success_count:  int  = 0
    failure_count:  int  = 0
    avg_duration_s: float = 0.0
    _durations:     List[float] = field(default_factory=list, repr=False)

    def start(self) -> float:
        self.last_run_at = _now_baghdad()
        self.last_status = "running"
        self.last_error  = ""
        self.run_count  += 1
        return time.time()

    def finish(self, start_t: float, success: bool, error: str = "") -> None:
        dur = time.time() - start_t
        self._durations.append(dur)
        if len(self._durations) > 20:
            self._durations.pop(0)
        self.avg_duration_s = sum(self._durations) / len(self._durations)
        if success:
            self.success_count += 1
            self.last_status = "success"
        else:
            self.failure_count += 1
            self.last_status = "failure"
            self.last_error = error[:500]

    def as_dict(self) -> dict:
        d = asdict(self)
        d.pop("_durations", None)
        return d


class HealthMonitor:
    """Singleton-friendly health tracker for all pipeline stages."""

    def __init__(self, telegram_token: str = "", telegram_chat_id: str = ""):
        self._token   = telegram_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self._chat_id = telegram_chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self._stages: Dict[str, PipelineStatus] = {}
        self._heartbeat_file = STATUS_FILE

    # ── stage management ───────────────────────────────────────────────────
    def stage(self, name: str) -> PipelineStatus:
        if name not in self._stages:
            self._stages[name] = PipelineStatus(name=name)
        return self._stages[name]

    def start_stage(self, name: str) -> float:
        t = self.stage(name).start()
        self._persist()
        logger.info("[%s] started", name)
        return t

    def finish_stage(self, name: str, start_t: float,
                     success: bool, error: str = "") -> None:
        self.stage(name).finish(start_t, success, error)
        self._persist()
        if success:
            logger.info("[%s] ✓ success (%.1fs)", name, time.time() - start_t)
        else:
            logger.error("[%s] ✗ failure — %s", name, error)
            self._alert_failure(name, error)

    # ── persist ────────────────────────────────────────────────────────────
    def _persist(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._heartbeat_file), exist_ok=True)
            snapshot = {
                "updated_at": _now_baghdad(),
                "stages": {k: v.as_dict() for k, v in self._stages.items()},
            }
            with open(self._heartbeat_file, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.warning("Could not persist health status: %s", exc)

    # ── Telegram helpers ───────────────────────────────────────────────────
    def _send_telegram(self, text: str) -> None:
        if not self._token or not self._chat_id:
            return
        try:
            import requests
            url = f"https://api.telegram.org/bot{self._token}/sendMessage"
            requests.post(url, data={"chat_id": self._chat_id, "text": text, "parse_mode": "HTML"}, timeout=15)
        except Exception as exc:
            logger.warning("Telegram send failed: %s", exc)

    def _alert_failure(self, stage: str, error: str) -> None:
        self._send_telegram(
            f"🔴 <b>Pipeline Failure</b>\n"
            f"Stage: <code>{stage}</code>\n"
            f"Time: {_now_baghdad()}\n"
            f"Error: {error[:300]}"
        )

    def alert_critical(self, title: str, detail: str) -> None:
        logger.critical("%s — %s", title, detail)
        self._send_telegram(f"💥 <b>{title}</b>\n{detail[:400]}")

    def send_success_summary(self, title: str, details: str) -> None:
        self._send_telegram(f"✅ <b>{title}</b>\n{details}")

    # ── full report ────────────────────────────────────────────────────────
    def summary_report(self) -> str:
        lines = [f"📊 <b>Pipeline Status — {_now_baghdad()}</b>", ""]
        for name, st in self._stages.items():
            icon = {"success": "✅", "failure": "❌", "running": "🔄",
                    "pending": "⏸", "skipped": "⏭"}.get(st.last_status, "•")
            lines.append(
                f"{icon} <b>{name}</b>: {st.last_status} "
                f"(runs={st.run_count}, ok={st.success_count}, err={st.failure_count}, "
                f"avg={st.avg_duration_s:.1f}s)"
            )
            if st.last_error:
                lines.append(f"   ↳ {st.last_error[:120]}")
        return "\n".join(lines)

    def send_summary_report(self) -> None:
        self._send_telegram(self.summary_report())

    # ── retry statistics ───────────────────────────────────────────────────
    def log_retry_stats(self, operation: str, attempts: int, final: str) -> None:
        logger.info("Retry stats — op=%s attempts=%d final=%s", operation, attempts, final)
        if attempts > 1:
            self._send_telegram(
                f"⚠️ <b>Retry Notice</b>\n"
                f"Operation: {operation}\n"
                f"Attempts: {attempts}\n"
                f"Result: {final}"
            )


# Global default instance (configure in main.py / scripts)
monitor = HealthMonitor()


# ── CLI entry point ────────────────────────────────────────────────────────
def _cli_report() -> None:
    """Run health checks and report via Telegram + stdout."""
    import sys
    import requests as _requests

    checks, issues = [], []
    now_str = _now_baghdad()

    def ok(name: str) -> None:
        checks.append(f"✅ {name}")

    def fail(name: str, reason: str) -> None:
        checks.append(f"❌ {name}: {reason}")
        issues.append(name)

    # Check required secrets / env vars
    for key in ["GEMINI_API_KEY_1", "IG_ACCESS_TOKEN", "GOOGLE_SHEET_ID",
                "SUPABASE_URL", "SUPABASE_SECRET_KEY"]:
        val = os.environ.get(key, "")
        if val:
            ok(key)
        else:
            fail(key, "not set")

    # Check optional keys
    for key in ["GEMINI_API_KEY_2", "GEMINI_API_KEY_3"]:
        val = os.environ.get(key, "")
        if val:
            ok(key)
        else:
            checks.append(f"⚠️ {key}: not set (optional)")

    status = "🟢 All checks passed" if not issues else f"🔴 {len(issues)} checks failed"
    msg = (
        f"<b>Health — {now_str}</b>\n\n"
        + "\n".join(checks)
        + f"\n\n<b>{status}</b>"
    )

    print(msg)

    # Send to Telegram
    tok  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if tok and chat:
        try:
            _requests.post(
                f"https://api.telegram.org/bot{tok}/sendMessage",
                data={"chat_id": chat, "text": msg, "parse_mode": "HTML"},
                timeout=15,
            )
        except Exception as e:
            print(f"Telegram send failed: {e}", file=sys.stderr)

    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Health Monitor CLI")
    parser.add_argument("--report", action="store_true", help="Run health checks and report")
    args = parser.parse_args()
    if args.report:
        _cli_report()
