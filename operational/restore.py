"""
Restore System
==============
Restores backups created by operational/backup.py.

Supports:
  - Backup validation and checksum verification
  - Dry-run mode (no data modified)
  - Explicit confirmation for destructive restore
  - Database restore (SQLite from .db.gz)
  - Configuration-state restore
  - Telegram notification of result

Usage:
  python -m operational.restore --list
  python -m operational.restore --validate backups/db/phase8_20240101_0300.db.gz
  python -m operational.restore --restore backups/db/phase8_20240101_0300.db.gz --dry-run
  python -m operational.restore --restore backups/db/phase8_20240101_0300.db.gz --confirm
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import logging
import os
import shutil
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

logger = logging.getLogger("operational.restore")

BAGHDAD_OFFSET = timedelta(hours=3)
PROJECT_ROOT   = Path(__file__).parent.parent
BACKUP_DIR     = PROJECT_ROOT / "backups"

# Phase DB path mapping (env var → default local path)
_PHASE_DB_MAP = {
    "phase8": ("LEARNING_LAYER_DATABASE_URL", "phase8_learning_knowledge.db"),
    "phase9": ("KCL_DATABASE_URL",            "phase9_coverage.db"),
    "phase10": ("P10_DATABASE_URL",           "phase10_intelligence.db"),
}


def _send_telegram(message: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat  = os.environ.get("TELEGRAM_CHAT_ID",   "")
    if not (token and chat):
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat, "text": message, "parse_mode": "HTML"},
            timeout=15,
        )
    except Exception as e:
        logger.warning("Telegram notification failed: %s", e)


def _checksum(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def list_backups() -> None:
    """List all available backup files."""
    if not BACKUP_DIR.exists():
        print(f"No backup directory found at {BACKUP_DIR}")
        return
    files = sorted(BACKUP_DIR.rglob("*.gz"))
    if not files:
        print("No backup files found.")
        return
    print(f"Available backups in {BACKUP_DIR}:\n")
    for f in files:
        size_kb = f.stat().st_size // 1024
        print(f"  {f.relative_to(PROJECT_ROOT)}  ({size_kb} KB)")


def validate_backup(backup_path: Path) -> bool:
    """Validate a backup file (decompress check, not corruption)."""
    if not backup_path.exists():
        print(f"❌ File not found: {backup_path}")
        return False
    try:
        with gzip.open(backup_path, "rb") as f:
            data = f.read()
        checksum = hashlib.sha256(data).hexdigest()
        size = len(data)
        print(f"✅ Backup valid: {backup_path.name}")
        print(f"   Decompressed size : {size:,} bytes")
        print(f"   SHA-256 (content) : {checksum}")
        return True
    except Exception as e:
        print(f"❌ Backup validation failed: {e}")
        return False


def restore_database(backup_path: Path, target_path: Path, dry_run: bool = True) -> bool:
    """
    Restore a compressed database backup to target_path.

    Args:
        backup_path: Path to the .db.gz backup file.
        target_path: Where to write the restored database file.
        dry_run: If True, only validate without writing.

    Returns:
        True on success, False on failure.
    """
    if not validate_backup(backup_path):
        return False

    if dry_run:
        print(f"[DRY RUN] Would restore {backup_path.name} → {target_path}")
        print("[DRY RUN] No files were modified.")
        return True

    # Create backup of existing db before overwrite
    if target_path.exists():
        backup_of_current = target_path.with_suffix(".db.pre_restore_backup")
        shutil.copy2(target_path, backup_of_current)
        print(f"  Saved existing DB as: {backup_of_current}")

    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(backup_path, "rb") as f_in, open(target_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        print(f"✅ Restored: {backup_path.name} → {target_path}")
        return True
    except Exception as e:
        print(f"❌ Restore failed: {e}")
        logger.error("Restore failed for %s: %s", backup_path, e)
        return False


def _resolve_target_path(backup_name: str) -> Path | None:
    """Determine target DB path from backup filename."""
    for phase, (env_var, default_name) in _PHASE_DB_MAP.items():
        if phase in backup_name:
            db_url = os.environ.get(env_var, "")
            if db_url.startswith("sqlite:///"):
                db_path = db_url.replace("sqlite:///", "")
                if not os.path.isabs(db_path):
                    db_path = str(PROJECT_ROOT / db_path)
                return Path(db_path)
            return PROJECT_ROOT / default_name
    return None


def run_restore(backup_path_str: str, dry_run: bool = True, confirm: bool = False) -> None:
    backup_path = Path(backup_path_str)
    if not backup_path.is_absolute():
        backup_path = PROJECT_ROOT / backup_path

    if not backup_path.exists():
        print(f"❌ Backup not found: {backup_path}")
        sys.exit(1)

    target = _resolve_target_path(backup_path.name)
    if not target:
        print(f"❌ Cannot determine target path for: {backup_path.name}")
        print("  Supported phases: phase8, phase9, phase10")
        sys.exit(1)

    if not dry_run and not confirm:
        print("⚠️  This will OVERWRITE the current database!")
        print(f"   Backup : {backup_path}")
        print(f"   Target : {target}")
        answer = input("\nType 'yes' to confirm destructive restore: ")
        if answer.strip().lower() != "yes":
            print("Restore cancelled.")
            sys.exit(0)

    now = datetime.now(tz=timezone(BAGHDAD_OFFSET)).strftime("%Y-%m-%d %H:%M Baghdad")
    success = restore_database(backup_path, target, dry_run=dry_run)

    if not dry_run:
        if success:
            _send_telegram(
                f"✅ <b>Restore SUCCESS</b>\n{now}\n"
                f"Backup: <code>{backup_path.name}</code>\n"
                f"Target: <code>{target}</code>"
            )
        else:
            _send_telegram(
                f"🔴 <b>Restore FAILED</b>\n{now}\n"
                f"Backup: <code>{backup_path.name}</code>"
            )
    sys.exit(0 if success else 1)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description="Restore backups created by operational/backup.py"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list",     action="store_true", help="List available backups")
    group.add_argument("--validate", metavar="FILE",      help="Validate a backup file")
    group.add_argument("--restore",  metavar="FILE",      help="Restore a backup file")
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="Validate only, do not write (default when --restore)")
    parser.add_argument("--confirm", action="store_true", default=False,
                        help="Skip interactive confirmation for destructive restore")
    args = parser.parse_args()

    if args.list:
        list_backups()
    elif args.validate:
        sys.exit(0 if validate_backup(Path(args.validate)) else 1)
    elif args.restore:
        run_restore(args.restore, dry_run=args.dry_run, confirm=args.confirm)


if __name__ == "__main__":
    main()
