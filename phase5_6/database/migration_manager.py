"""
Migration manager.

Responsible for:
  1. Making sure `schema_version` exists.
  2. On a completely fresh database, applying the baseline
     (schema.sql -> indexes.sql -> functions.sql -> triggers.sql -> views.sql)
     as version 1.
  3. Discovering every *.sql file in database/migrations/, in numeric-prefix
     order, and applying any whose version is newer than what's recorded.
  4. Recording the new version after each successful migration, inside the
     same transaction as the migration itself (so a failure never leaves a
     half-applied migration marked as done).
  5. Retrying transient connection errors, and raising a clear, final error
     (for migrate.py to report via Telegram) when a migration fails for real.

No other module should read database/migrations/ directly.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError

logger = logging.getLogger("database.migration_manager")

DATABASE_DIR = Path(__file__).resolve().parent
MIGRATIONS_DIR = DATABASE_DIR / "migrations"

BASELINE_VERSION = 1
BASELINE_NAME = "0001_initial_schema"
BASELINE_FILES = [
    DATABASE_DIR / "schema.sql",
    DATABASE_DIR / "indexes.sql",
    DATABASE_DIR / "functions.sql",
    DATABASE_DIR / "triggers.sql",
    DATABASE_DIR / "views.sql",
]

MIGRATION_FILENAME_RE = re.compile(r"^(\d{4,})_([a-zA-Z0-9_]+)\.sql$")

RETRYABLE_ATTEMPTS = 3
RETRYABLE_BASE_SECONDS = 2


class MigrationError(Exception):
    """A migration failed after all retries. Non-retryable / final."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    path: Path

    @property
    def sql(self) -> str:
        return self.path.read_text(encoding="utf-8")


def _is_transient(error: OperationalError) -> bool:
    """Heuristic for 'worth retrying' vs 'a genuinely broken migration'.
    Connection resets / timeouts / server-not-ready are transient; SQL
    syntax errors or constraint violations surface as ProgrammingError /
    IntegrityError and are never retried."""
    message = str(error).lower()
    transient_markers = (
        "could not connect", "connection reset", "connection refused",
        "timeout", "server closed the connection", "terminating connection",
        "the database system is starting up",
    )
    return any(marker in message for marker in transient_markers)


def discover_migrations() -> List[Migration]:
    """Returns migrations/*.sql sorted by numeric prefix. The baseline
    (version 1) is NOT included here — it lives in BASELINE_FILES and is
    applied separately by ensure_baseline(). File names must look like
    0002_add_something.sql; anything else is skipped with a warning."""
    if not MIGRATIONS_DIR.exists():
        return []

    migrations: List[Migration] = []
    for path in sorted(MIGRATIONS_DIR.iterdir()):
        if not path.is_file():
            continue
        match = MIGRATION_FILENAME_RE.match(path.name)
        if not match:
            if path.suffix == ".sql":
                logger.warning("Skipping migration file with unexpected name: %s", path.name)
            continue
        version = int(match.group(1))
        if version == BASELINE_VERSION:
            # 0001 is reserved for the baseline files above; a stray
            # migrations/0001_*.sql would silently never run otherwise.
            raise MigrationError(
                f"migrations/{path.name} uses version 1, which is reserved for the "
                f"baseline (schema.sql/indexes.sql/...). Start new migrations at 0002."
            )
        migrations.append(Migration(version=version, name=match.group(2), path=path))

    migrations.sort(key=lambda m: m.version)

    seen_versions = set()
    for m in migrations:
        if m.version in seen_versions:
            raise MigrationError(f"Duplicate migration version {m.version} in database/migrations/.")
        seen_versions.add(m.version)

    return migrations


class MigrationManager:
    def __init__(self, engine: Engine):
        self.engine = engine

    # -- schema_version bookkeeping -----------------------------------------

    def ensure_schema_version_table(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version      INTEGER PRIMARY KEY,
                    name         TEXT NOT NULL,
                    applied_at   TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            ))

    def get_current_version(self) -> int:
        with self.engine.connect() as conn:
            result = conn.execute(text("SELECT COALESCE(MAX(version), 0) FROM schema_version"))
            return int(result.scalar_one())

    # -- applying migrations ---------------------------------------------------

    def _run_with_retry(self, description: str, run_once) -> None:
        last_error: Optional[Exception] = None
        for attempt in range(1, RETRYABLE_ATTEMPTS + 1):
            try:
                run_once()
                return
            except OperationalError as e:
                last_error = e
                if not _is_transient(e) or attempt == RETRYABLE_ATTEMPTS:
                    raise MigrationError(f"{description} failed: {e}") from e
                wait = RETRYABLE_BASE_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "%s failed on attempt %d/%d with a transient error, retrying in %ds: %s",
                    description, attempt, RETRYABLE_ATTEMPTS, wait, e,
                )
                time.sleep(wait)
        if last_error:  # pragma: no cover - defensive
            raise MigrationError(f"{description} failed: {last_error}") from last_error

    def ensure_baseline(self) -> bool:
        """Applies schema.sql/indexes.sql/functions.sql/triggers.sql/views.sql
        as version 1, exactly once, inside a single transaction. Returns True
        if it applied the baseline just now, False if it was already applied."""
        if self.get_current_version() >= BASELINE_VERSION:
            return False

        missing = [f for f in BASELINE_FILES if not f.exists()]
        if missing:
            raise MigrationError(
                "Missing baseline SQL file(s): " + ", ".join(str(f) for f in missing)
            )

        def _apply() -> None:
            with self.engine.begin() as conn:
                for file_path in BASELINE_FILES:
                    logger.info("Applying baseline file: %s", file_path.name)
                    conn.execute(text(file_path.read_text(encoding="utf-8")))
                conn.execute(
                    text("INSERT INTO schema_version (version, name) VALUES (:v, :n)"),
                    {"v": BASELINE_VERSION, "n": BASELINE_NAME},
                )

        self._run_with_retry("Baseline schema creation (version 1)", _apply)
        logger.info("Baseline schema applied (version %d).", BASELINE_VERSION)
        return True

    def apply_migration(self, migration: Migration) -> None:
        def _apply() -> None:
            with self.engine.begin() as conn:
                conn.execute(text(migration.sql))
                conn.execute(
                    text("INSERT INTO schema_version (version, name) VALUES (:v, :n)"),
                    {"v": migration.version, "n": migration.name},
                )

        self._run_with_retry(f"Migration {migration.version:04d}_{migration.name}", _apply)
        logger.info("Applied migration %04d_%s.", migration.version, migration.name)

    def run_pending(self) -> List[str]:
        """Ensures schema_version exists, applies the baseline if needed,
        then applies every pending migrations/*.sql file in order. Returns
        the list of migration labels that were applied (for reporting)."""
        applied: List[str] = []

        self.ensure_schema_version_table()
        if self.ensure_baseline():
            applied.append(BASELINE_NAME)

        current_version = self.get_current_version()
        pending = [m for m in discover_migrations() if m.version > current_version]

        for migration in pending:
            self.apply_migration(migration)
            applied.append(f"{migration.version:04d}_{migration.name}")

        return applied
