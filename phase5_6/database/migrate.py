"""
Migration entrypoint.

Run this once at the start of any script/workflow that touches the database
(or on its own: `python -m database.migrate`). It will:

    1. Connect to the database (with retry).
    2. Ensure schema_version exists.
    3. Apply the baseline schema on a brand new database (version 1).
    4. Apply any new files under database/migrations/ in order.
    5. On success, log what was applied (silent no-op if nothing was pending).
    6. On failure, log the error and send a full Telegram report, then exit
       non-zero so the calling workflow stops rather than continuing against
       a database that isn't in the expected shape.

This is the ONLY supported way to change the schema. Never create or alter
tables by hand in the Supabase dashboard — add a new database/migrations/NNNN_*.sql
file instead and it will be picked up automatically next run.
"""
from __future__ import annotations

import logging
import os
import sys
import traceback
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.client import DatabaseConnectionError, get_engine
from database.migration_manager import MigrationError, MigrationManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("database.migrate")


def _notify_failure(title: str, detail: str) -> None:
    """Best-effort Telegram alert. Never raises — a notification failure
    must not mask the original migration failure."""
    try:
        from lib.config import optional_env
        from lib.telegram_notifier import TelegramNotifier

        bot_token = optional_env("TELEGRAM_BOT_TOKEN")
        chat_id = optional_env("TELEGRAM_CHAT_ID")
        if not bot_token or not chat_id:
            logger.warning("TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set — skipping Telegram alert.")
            return
        TelegramNotifier(bot_token, chat_id).alert_critical(title, detail)
    except Exception:
        logger.exception("Failed to send the Telegram failure report itself.")


def run() -> None:
    parser = argparse.ArgumentParser(description="Database migration and seeding.")
    parser.add_argument("--seed", action="store_true", help="Seed the database after migrating")
    args = parser.parse_args()

    logger.info("Starting database migration check...")
    try:
        engine = get_engine()
    except DatabaseConnectionError as e:
        logger.error("Could not connect to the database: %s", e)
        _notify_failure("فشل الاتصال بقاعدة البيانات", str(e))
        sys.exit(1)

    manager = MigrationManager(engine)
    try:
        applied = manager.run_pending()
    except MigrationError as e:
        logger.error("Migration failed: %s", e)
        _notify_failure("فشل تنفيذ Migration", str(e))
        sys.exit(1)
    except Exception as e:  # anything unforeseen still gets reported, then re-raised
        logger.error("Unexpected error while running migrations: %s", e)
        _notify_failure("خطأ غير متوقع أثناء تنفيذ Migrations", traceback.format_exc()[:3500])
        raise

    if applied:
        logger.info("Applied %d migration(s): %s", len(applied), ", ".join(applied))
    else:
        logger.info("Database is already up to date. Nothing to apply.")

    if args.seed:
        try:
            from database import seed
            seed.run()
        except Exception as e:
            logger.error("Unexpected error while seeding the database: %s", e)
            _notify_failure("خطأ غير متوقع أثناء تنفيذ Seeding", traceback.format_exc()[:3500])
            raise

if __name__ == "__main__":
    run()
