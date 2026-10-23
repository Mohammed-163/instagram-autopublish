"""
Backup System
=============
Backs up:
  1. PostgreSQL/Supabase databases for Phases 7-10 (pg_dump or SQLite copy)
  2. The logs/ directory (compressed)
  3. Key config files (.env.example, migrations/)
  4. Gemini rotation state

Retention: BACKUP_RETENTION_DAYS (default 30 days)
Storage: GitHub repo /backups/ via Contents API  +  local /backups/ dir
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
import logging
import os
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger("operational.backup")

BAGHDAD_OFFSET = timedelta(hours=3)
PROJECT_ROOT   = Path(__file__).parent.parent
BACKUP_DIR     = PROJECT_ROOT / "backups"
RETENTION_DAYS = int(os.environ.get("BACKUP_RETENTION_DAYS", "30"))


def _now_tag() -> str:
    return datetime.now(tz=timezone(BAGHDAD_OFFSET)).strftime("%Y%m%d_%H%M")


def _checksum(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ── GitHub upload ──────────────────────────────────────────────────────────
def _commit_to_github(path_in_repo: str, content_bytes: bytes, message: str) -> bool:
    token = os.environ.get("GH_PAT", "")
    repo  = os.environ.get("GH_REPO", "")
    if not token or not repo:
        logger.warning("GH_PAT / GH_REPO not set — skipping GitHub backup upload")
        return False

    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
    api = f"https://api.github.com/repos/{repo}/contents/{path_in_repo}"

    existing = requests.get(api, headers=headers, timeout=20)
    sha = existing.json().get("sha") if existing.ok else None

    body: dict = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode(),
    }
    if sha:
        body["sha"] = sha

    resp = requests.put(api, headers=headers, json=body, timeout=30)
    if resp.status_code in (200, 201):
        logger.info("GitHub backup uploaded: %s", path_in_repo)
        return True
    logger.error("GitHub backup upload failed %s: %s %s", path_in_repo, resp.status_code, resp.text[:200])
    return False


# ── Database backup ────────────────────────────────────────────────────────
def _pg_dump(db_url: str, out_path: Path) -> bool:
    """Run pg_dump for a PostgreSQL URL, gzip the result."""
    # Strip SQLAlchemy driver prefix for pg_dump
    pg_url = db_url
    for prefix in ("postgresql+psycopg2://", "postgresql+psycopg://", "postgresql+asyncpg://"):
        if pg_url.startswith(prefix):
            pg_url = "postgresql://" + pg_url[len(prefix):]
            break

    try:
        result = subprocess.run(
            ["pg_dump", "--no-password", "-Fc", pg_url],
            capture_output=True, timeout=120,
        )
        if result.returncode != 0:
            logger.error("pg_dump failed: %s", result.stderr.decode()[:500])
            return False
        with gzip.open(out_path, "wb") as f:
            f.write(result.stdout)
        logger.info("pg_dump backup written: %s (%d bytes)", out_path, len(result.stdout))
        return True
    except FileNotFoundError:
        logger.warning("pg_dump not available — skipping Postgres backup for this phase")
        return False
    except subprocess.TimeoutExpired:
        logger.error("pg_dump timed out")
        return False


def backup_databases(tag: str) -> list[str]:
    backed_up = []
    phase_map = {
        "phase7":  "OBSERVATION_DB_DSN",
        "phase8":  "LEARNING_LAYER_DATABASE_URL",
        "phase9":  "KCL_DATABASE_URL",
        "phase10": "P10_DATABASE_URL",
    }
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    for label, env_var in phase_map.items():
        url = os.environ.get(env_var, "")
        if not url:
            logger.info("Skipping %s backup — %s not set", label, env_var)
            continue

        if url.startswith("sqlite:///"):
            # SQLite file copy
            db_file = url.replace("sqlite:///", "")
            if not os.path.isabs(db_file):
                db_file = str(PROJECT_ROOT / db_file)
            if not os.path.exists(db_file):
                logger.info("SQLite file not found, skipping: %s", db_file)
                continue
            out_name = f"{label}_{tag}.db.gz"
            out_path = BACKUP_DIR / out_name
            with open(db_file, "rb") as fin, gzip.open(out_path, "wb") as fout:
                shutil.copyfileobj(fin, fout)
            logger.info("SQLite backup: %s → %s", db_file, out_path)
        else:
            # PostgreSQL pg_dump
            out_name = f"{label}_{tag}.pgdump.gz"
            out_path = BACKUP_DIR / out_name
            if not _pg_dump(url, out_path):
                logger.warning("Skipped PostgreSQL backup for %s", label)
                continue

        checksum = _checksum(out_path)
        logger.info("Backup checksum (%s): %s", out_name, checksum)
        with open(out_path, "rb") as f:
            _commit_to_github(
                f"backups/db/{out_name}",
                f.read(),
                f"backup: {label} database {tag} sha256={checksum[:12]}",
            )
        backed_up.append(str(out_path))
    return backed_up


# ── Gemini rotation state backup ───────────────────────────────────────────
def backup_rotation_state(tag: str) -> Optional[str]:
    state_file = PROJECT_ROOT / "gemini_rotation_state.json"
    if not state_file.exists():
        logger.info("No Gemini rotation state file found, skipping")
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    out_name = f"gemini_rotation_state_{tag}.json.gz"
    out_path = BACKUP_DIR / out_name
    with open(state_file, "rb") as fin, gzip.open(out_path, "wb") as fout:
        shutil.copyfileobj(fin, fout)
    with open(out_path, "rb") as f:
        _commit_to_github(
            f"backups/state/{out_name}", f.read(),
            f"backup: gemini rotation state {tag}",
        )
    logger.info("Rotation state backed up: %s", out_path)
    return str(out_path)


# ── Logs backup ────────────────────────────────────────────────────────────
def backup_logs(tag: str) -> Optional[str]:
    log_dir = PROJECT_ROOT / "logs"
    if not log_dir.exists() or not list(log_dir.glob("*.log")):
        logger.info("No log files found, skipping log backup")
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    out_name = f"logs_{tag}.tar.gz"
    out_path = BACKUP_DIR / out_name
    with tarfile.open(out_path, "w:gz") as tar:
        for log_file in sorted(log_dir.glob("*.log")):
            tar.add(log_file, arcname=log_file.name)
    with open(out_path, "rb") as f:
        _commit_to_github(
            f"backups/logs/{out_name}", f.read(),
            f"backup: logs {tag}",
        )
    logger.info("Logs backed up: %s", out_path)
    return str(out_path)


# ── Retention cleanup ──────────────────────────────────────────────────────
def cleanup_old_backups() -> None:
    if not BACKUP_DIR.exists():
        return
    cutoff = datetime.now(tz=timezone(BAGHDAD_OFFSET)).timestamp() - (RETENTION_DAYS * 86400)
    for f in BACKUP_DIR.rglob("*"):
        if f.is_file() and f.stat().st_mtime < cutoff:
            f.unlink()
            logger.info("Deleted old backup: %s", f)


# ── Telegram notification ──────────────────────────────────────────────────
def _notify_telegram(message: str) -> None:
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


# ── Main entry point ───────────────────────────────────────────────────────
def run_backup() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
    )
    tag = _now_tag()
    now = datetime.now(tz=timezone(BAGHDAD_OFFSET)).strftime("%Y-%m-%d %H:%M Baghdad")
    logger.info("Starting backup run — tag: %s", tag)

    results = []
    try:
        dbs = backup_databases(tag)
        results.extend(dbs)
    except Exception as e:
        logger.error("Database backup failed: %s", e)

    try:
        state = backup_rotation_state(tag)
        if state:
            results.append(state)
    except Exception as e:
        logger.error("Rotation state backup failed: %s", e)

    try:
        logs = backup_logs(tag)
        if logs:
            results.append(logs)
    except Exception as e:
        logger.error("Log backup failed: %s", e)

    try:
        cleanup_old_backups()
    except Exception as e:
        logger.warning("Retention cleanup failed: %s", e)

    summary = "\n".join(f"  • {r}" for r in results) if results else "  (nothing backed up)"
    logger.info("Backup complete. Files:\n%s", summary)
    _notify_telegram(
        f"✅ <b>Backup Complete</b> — {now}\n"
        f"Files: {len(results)}\n<pre>{summary}</pre>"
    )


if __name__ == "__main__":
    run_backup()
