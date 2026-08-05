"""
Unified database configuration helper.

Resolves the correct SQLAlchemy database URL for each phase using
the following priority:

  1. Phase-specific env var (e.g. LEARNING_LAYER_DATABASE_URL)
  2. Shared DATABASE_URL env var
  3. Derived from SUPABASE_URL + SUPABASE_SECRET_KEY (Supabase connection pooler)
  4. In-memory SQLite ONLY when ALLOW_SQLITE_FALLBACK=true (tests only)

Production workflows must set either a phase-specific URL, DATABASE_URL,
or valid SUPABASE_* credentials. Silently falling back to SQLite in
production is explicitly rejected.
"""
from __future__ import annotations

import logging
import os
import re
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger("operational.db_config")

_SQLITE_FALLBACK_ALLOWED = os.environ.get("ALLOW_SQLITE_FALLBACK", "").lower() in ("1", "true", "yes")


def _derive_from_supabase() -> str | None:
    """
    Attempt to build a PostgreSQL DSN from SUPABASE_URL and SUPABASE_SECRET_KEY.

    Supabase connection string format (transaction pooler, port 6543):
      postgresql+psycopg2://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres

    We derive this from the Supabase project API URL:
      https://[project-ref].supabase.co
    """
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_SECRET_KEY", "")
    if not supabase_url or not supabase_key:
        return None

    # Extract project ref from https://<ref>.supabase.co
    m = re.match(r"https?://([^.]+)\.supabase\.co", supabase_url)
    if not m:
        logger.warning("Cannot parse project ref from SUPABASE_URL: %s", supabase_url)
        return None

    project_ref = m.group(1)
    # Use Supabase connection pooler (transaction mode, port 6543)
    # Password is the service_role / secret key
    dsn = (
        f"postgresql+psycopg2://postgres.{project_ref}:{supabase_key}"
        f"@aws-0-eu-central-1.pooler.supabase.com:6543/postgres"
    )
    logger.info("Derived DATABASE_URL from SUPABASE_URL (project: %s***)", project_ref[:8])
    return dsn


def resolve_database_url(phase_var: str, default_sqlite: str = "") -> str:
    """
    Resolve the database URL for a given phase.

    Args:
        phase_var: Phase-specific env var name (e.g. 'LEARNING_LAYER_DATABASE_URL').
        default_sqlite: SQLite path used ONLY when ALLOW_SQLITE_FALLBACK=true.

    Returns:
        A valid SQLAlchemy database URL string.

    Raises:
        RuntimeError: When no valid production URL can be resolved and
                      SQLite fallback is not allowed.
    """
    # 1. Phase-specific var
    url = os.environ.get(phase_var, "")
    if url:
        _warn_if_sqlite(url, phase_var)
        return url

    # 2. Shared DATABASE_URL
    url = os.environ.get("DATABASE_URL", "")
    if url:
        _warn_if_sqlite(url, "DATABASE_URL")
        return url

    # 3. Derive from Supabase credentials
    url = _derive_from_supabase()
    if url:
        return url

    # 4. SQLite fallback — tests only
    if _SQLITE_FALLBACK_ALLOWED and default_sqlite:
        logger.warning(
            "ALLOW_SQLITE_FALLBACK is set — using SQLite for %s. "
            "This is NOT safe for production.",
            phase_var,
        )
        return default_sqlite

    raise RuntimeError(
        f"No database URL available for {phase_var}. "
        f"Set {phase_var}, DATABASE_URL, or SUPABASE_URL + SUPABASE_SECRET_KEY. "
        f"SQLite fallback requires ALLOW_SQLITE_FALLBACK=true (tests only)."
    )


def _warn_if_sqlite(url: str, source: str) -> None:
    if url.startswith("sqlite"):
        if not _SQLITE_FALLBACK_ALLOWED:
            raise RuntimeError(
                f"SQLite URL detected in {source} but ALLOW_SQLITE_FALLBACK is not set. "
                "Production databases must use PostgreSQL."
            )
        logger.warning("SQLite in use for %s — safe only for tests.", source)
