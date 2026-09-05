"""
Database connection layer.

Builds a SQLAlchemy 2.x engine for the project's Supabase Postgres database
from the two secrets configured in GitHub:

    SUPABASE_URL         e.g. https://abcdefghij.supabase.co
    SUPABASE_SECRET_KEY  the project's service_role secret key

Supabase's REST/API secrets are not, strictly speaking, a Postgres
connection string. To keep the "only two secrets" requirement, we derive the
direct Postgres connection from the project ref embedded in SUPABASE_URL and
use SUPABASE_SECRET_KEY as the database password (Supabase provisions the
`postgres` role's password to equal the service_role secret key on projects
created for direct DB access via that key). If your project's DB password
was rotated independently and no longer matches the secret key, set the
optional override below instead of changing any application code:

    DATABASE_URL           full SQLAlchemy URL, used verbatim if present
    SUPABASE_DB_PASSWORD    overrides the derived password only

Every other module in the project must go through `get_engine()` /
`get_session()` here — never construct a connection anywhere else.
"""
from __future__ import annotations

import logging
import re
import time
from contextlib import contextmanager
from typing import Iterator, Optional
from urllib.parse import quote_plus, urlparse

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from lib.config import optional_env, require_env

logger = logging.getLogger("database.client")

# ---------------------------------------------------------------------------
# Retry / connection tuning
# ---------------------------------------------------------------------------
CONNECT_MAX_ATTEMPTS = 5
CONNECT_RETRY_BASE_SECONDS = 2  # exponential backoff: 2, 4, 8, 16, 32
SUPABASE_DB_PORT = 5432
SUPABASE_DB_NAME = "postgres"
SUPABASE_DB_USER = "postgres"


class DatabaseConnectionError(Exception):
    """Raised when the database could not be reached after all retries."""


def _project_ref_from_supabase_url(supabase_url: str) -> str:
    """Extracts `abcdefghij` out of `https://abcdefghij.supabase.co`."""
    host = urlparse(supabase_url).hostname or ""
    match = re.match(r"^([a-zA-Z0-9]+)\.supabase\.co$", host)
    if not match:
        raise DatabaseConnectionError(
            f"Could not extract a Supabase project ref from SUPABASE_URL={supabase_url!r}. "
            "Expected the form https://<project-ref>.supabase.co, or set DATABASE_URL directly."
        )
    return match.group(1)


def _build_database_url() -> str:
    explicit_url = optional_env("DATABASE_URL")
    if explicit_url:
        return explicit_url

    allow_sqlite = optional_env("ALLOW_SQLITE_FALLBACK", "").lower() in {"1", "true", "yes", "on"}
    running_in_ci = optional_env("CI", "").lower() == "true"
    supabase_url = optional_env("SUPABASE_URL")
    if not supabase_url and (allow_sqlite or running_in_ci):
        fallback_url = "sqlite:///./phase5_6_ci.db"
        logger.warning(
            "SUPABASE_URL is missing; using SQLite fallback because "
            "ALLOW_SQLITE_FALLBACK/CI permits it: %s",
            fallback_url,
        )
        return fallback_url

    if not supabase_url:
        supabase_url = require_env("SUPABASE_URL")
    secret_key = require_env("SUPABASE_SECRET_KEY")
    password = optional_env("SUPABASE_DB_PASSWORD") or secret_key

    project_ref = _project_ref_from_supabase_url(supabase_url)
    host = f"db.{project_ref}.supabase.co"

    return (
        f"postgresql+psycopg://{SUPABASE_DB_USER}:{quote_plus(password)}"
        f"@{host}:{SUPABASE_DB_PORT}/{SUPABASE_DB_NAME}?sslmode=require"
    )


_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None


def get_engine() -> Engine:
    """Returns a process-wide singleton engine, creating + connect-testing it
    on first call with retry for transient network failures."""
    global _engine, _session_factory
    if _engine is not None:
        return _engine

    database_url = _build_database_url()
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_recycle=1800,
        future=True,
    )

    last_error: Optional[Exception] = None
    for attempt in range(1, CONNECT_MAX_ATTEMPTS + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Connected to database (attempt %d/%d).", attempt, CONNECT_MAX_ATTEMPTS)
            break
        except OperationalError as e:
            last_error = e
            wait = CONNECT_RETRY_BASE_SECONDS * (2 ** (attempt - 1))
            logger.warning(
                "Database connection attempt %d/%d failed: %s. Retrying in %ds...",
                attempt, CONNECT_MAX_ATTEMPTS, e, wait,
            )
            if attempt < CONNECT_MAX_ATTEMPTS:
                time.sleep(wait)
    else:
        raise DatabaseConnectionError(
            f"Could not connect to the database after {CONNECT_MAX_ATTEMPTS} attempts: {last_error}"
        )

    _engine = engine
    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def get_session_factory() -> sessionmaker:
    if _session_factory is None:
        get_engine()
    assert _session_factory is not None
    return _session_factory


@contextmanager
def get_session() -> Iterator[Session]:
    """Context manager giving a Session with automatic commit/rollback.

    Usage:
        with get_session() as session:
            session.add(obj)
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine_for_tests() -> None:
    """Test-only helper to force re-derivation of the connection on the next call."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
