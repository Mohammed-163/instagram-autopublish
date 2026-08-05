"""
Operational Scheduler
======================
Runs all pipeline jobs on their configured schedules.
Timezone: Asia/Baghdad (UTC+3)

Jobs and their default schedules (all overridable via env vars):
  measurement   — daily  05:00  (generate posts)
  publish       — every  15 min (publish due posts)
  learning      — daily  03:00  (learning layer cycle)
  strategy      — daily  04:00  (strategy planning cycle)
  decision      — daily  04:30  (decision layer cycle)
  cleanup       — daily  23:00  (remove drive files for published posts)
  fetch_insights— daily  08:00  (fetch IG performance data, 3 days lag)
  token_refresh — weekly Sunday 02:00
  backup        — weekly Sunday 03:00
  health_check  — every  30 min
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import Callable

logger = logging.getLogger("operational.scheduler")

try:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
    _HAS_APScheduler = True
except ImportError:
    _HAS_APScheduler = False
    logger.warning("APScheduler not installed — scheduler cannot start.")

TIMEZONE = os.environ.get("SCHEDULER_TIMEZONE", "Asia/Baghdad")

# ── schedule config (env-overridable) ──────────────────────────────────────
def _cron(env_key: str, default: str) -> str:
    return os.environ.get(env_key, default)


_SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "phase5_6", "scripts")


def _run_script(name: str) -> None:
    """Run a phase5_6 script as a subprocess, streaming output to logger."""
    path = os.path.join(_SCRIPTS_DIR, name)
    logger.info("Running script: %s", path)
    try:
        result = subprocess.run(
            [sys.executable, path],
            capture_output=True, text=True, timeout=3600
        )
        if result.stdout:
            for line in result.stdout.splitlines():
                logger.info("[%s] %s", name, line)
        if result.returncode != 0:
            err = result.stderr[:500] if result.stderr else "(no stderr)"
            logger.error("[%s] exited with code %d: %s", name, result.returncode, err)
        else:
            logger.info("[%s] completed successfully", name)
    except subprocess.TimeoutExpired:
        logger.error("[%s] timed out after 3600s", name)
    except Exception as exc:
        logger.exception("[%s] failed: %s", name, exc)


def _run_main() -> None:
    """Run main.py (full AI system bootstrap cycle)."""
    main_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py"
    )
    logger.info("Running main bootstrap: %s", main_path)
    try:
        result = subprocess.run(
            [sys.executable, main_path],
            capture_output=True, text=True, timeout=1800
        )
        for line in (result.stdout or "").splitlines():
            logger.info("[main] %s", line)
        if result.returncode != 0:
            logger.error("[main] failed: %s", result.stderr[:400])
    except Exception as exc:
        logger.exception("[main] exception: %s", exc)


def build_scheduler() -> "BlockingScheduler":
    if not _HAS_APScheduler:
        raise RuntimeError("APScheduler is required: pip install apscheduler")

    sched = BlockingScheduler(timezone=TIMEZONE)

    def _job(fn: Callable, job_id: str) -> None:
        from operational.health_monitor import monitor
        import time
        t = monitor.start_stage(job_id)
        try:
            fn()
            monitor.finish_stage(job_id, t, success=True)
        except Exception as exc:
            monitor.finish_stage(job_id, t, success=False, error=str(exc))

    # ── Measurement / daily generation ─────────────────────────────────────
    sched.add_job(
        lambda: _job(lambda: _run_script("daily_generate.py"), "measurement"),
        CronTrigger.from_crontab(_cron("SCHEDULE_MEASUREMENT", "0 5 * * *"), timezone=TIMEZONE),
        id="measurement", name="Daily Post Generation",
    )

    # ── Publisher (every 15 min) ───────────────────────────────────────────
    sched.add_job(
        lambda: _job(lambda: _run_script("publish.py"), "publish"),
        CronTrigger.from_crontab(_cron("SCHEDULE_PUBLISH", "*/15 * * * *"), timezone=TIMEZONE),
        id="publish", name="Instagram Publisher",
    )

    # ── AI Learning cycle ──────────────────────────────────────────────────
    sched.add_job(
        lambda: _job(_run_main, "learning"),
        CronTrigger.from_crontab(_cron("SCHEDULE_LEARNING", "0 3 * * *"), timezone=TIMEZONE),
        id="learning", name="Learning Layer Cycle",
    )

    # ── Strategy planning ──────────────────────────────────────────────────
    sched.add_job(
        lambda: _job(lambda: _run_script("monthly_task.py"), "strategy"),
        CronTrigger.from_crontab(_cron("SCHEDULE_STRATEGY", "0 4 1 * *"), timezone=TIMEZONE),
        id="strategy", name="Monthly Strategy Planning",
    )

    # ── Cleanup (2h after publish window) ─────────────────────────────────
    sched.add_job(
        lambda: _job(lambda: _run_script("cleanup.py"), "cleanup"),
        CronTrigger.from_crontab(_cron("SCHEDULE_CLEANUP", "0 23 * * *"), timezone=TIMEZONE),
        id="cleanup", name="Drive Cleanup",
    )

    # ── Fetch Instagram insights ───────────────────────────────────────────
    sched.add_job(
        lambda: _job(lambda: _run_script("fetch_insights.py"), "fetch_insights"),
        CronTrigger.from_crontab(_cron("SCHEDULE_INSIGHTS", "0 8 * * *"), timezone=TIMEZONE),
        id="fetch_insights", name="Fetch IG Insights",
    )

    # ── Token refresh (weekly) ─────────────────────────────────────────────
    sched.add_job(
        lambda: _job(lambda: _run_script("refresh_token.py"), "token_refresh"),
        CronTrigger.from_crontab(_cron("SCHEDULE_TOKEN_REFRESH", "0 2 * * 0"), timezone=TIMEZONE),
        id="token_refresh", name="Meta Token Refresh",
    )

    # ── Backup (weekly) ───────────────────────────────────────────────────
    sched.add_job(
        lambda: _job(lambda: _run_script("weekly_backup.py"), "backup"),
        CronTrigger.from_crontab(_cron("SCHEDULE_BACKUP", "0 3 * * 0"), timezone=TIMEZONE),
        id="backup", name="Weekly Backup",
    )

    # ── Health check summary ───────────────────────────────────────────────
    sched.add_job(
        lambda: _job(lambda: __import__("operational.health_monitor", fromlist=["monitor"]).monitor.send_summary_report(), "health_check"),
        CronTrigger.from_crontab(_cron("SCHEDULE_HEALTH", "*/30 * * * *"), timezone=TIMEZONE),
        id="health_check", name="Health Check",
    )

    # ── Event listeners ───────────────────────────────────────────────────
    def _on_error(event):
        logger.error("Scheduler job failed: %s — %s", event.job_id, event.exception)

    def _on_executed(event):
        logger.debug("Scheduler job executed: %s", event.job_id)

    sched.add_listener(_on_error,    EVENT_JOB_ERROR)
    sched.add_listener(_on_executed, EVENT_JOB_EXECUTED)

    return sched


def run() -> None:
    """Start the blocking scheduler. Call from CLI or systemd service."""
    from operational.logging_config import setup
    setup(script_name="scheduler")
    logger.info("Starting Autonomous AI Scheduler (tz=%s)", TIMEZONE)
    sched = build_scheduler()
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
        sched.shutdown()


if __name__ == "__main__":
    run()
