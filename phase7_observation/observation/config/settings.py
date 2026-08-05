"""
Configuration module for Phase 7 Observation Layer.

Priority for database connection:
  1. OBSERVATION_DB_DSN (phase-specific)
  2. DATABASE_URL (shared)
  3. Derived from SUPABASE_URL + SUPABASE_SECRET_KEY
  4. SQLite ONLY when ALLOW_SQLITE_FALLBACK=true (tests)
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

# Add project root to path for operational modules
_PHASE7_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PROJECT_ROOT = os.path.dirname(_PHASE7_ROOT)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _resolve_db_dsn() -> str:
    """Resolve DB DSN with fallback chain."""
    # Direct phase-specific var
    v = os.environ.get("OBSERVATION_DB_DSN", "")
    if v:
        return v
    # Shared DATABASE_URL
    v = os.environ.get("DATABASE_URL", "")
    if v:
        return v
    # Supabase derivation
    try:
        from operational.db_config import resolve_database_url
        return resolve_database_url(
            "OBSERVATION_DB_DSN",
            "sqlite:///./phase7_observation.db",
        )
    except Exception:
        pass
    # Local dev fallback
    if os.environ.get("ALLOW_SQLITE_FALLBACK", "").lower() in ("1", "true", "yes"):
        return "sqlite:///./phase7_observation.db"
    raise RuntimeError(
        "No database URL for Phase 7. Set OBSERVATION_DB_DSN, DATABASE_URL, "
        "or SUPABASE_URL+SUPABASE_SECRET_KEY. SQLite requires ALLOW_SQLITE_FALLBACK=true."
    )


@dataclass(frozen=True)
class DatabaseSettings:
    dsn: str = field(default_factory=_resolve_db_dsn)
    pool_size: int = field(default_factory=lambda: int(_env("OBSERVATION_DB_POOL_SIZE", "5")))
    max_overflow: int = field(default_factory=lambda: int(_env("OBSERVATION_DB_MAX_OVERFLOW", "10")))
    echo_sql: bool = field(default_factory=lambda: _env("OBSERVATION_DB_ECHO", "false").lower() == "true")


@dataclass(frozen=True)
class VersionSettings:
    schema_version: str = field(default_factory=lambda: _env("OBSERVATION_SCHEMA_VERSION", "1.0"))
    observation_version: str = field(default_factory=lambda: _env("OBSERVATION_OBSERVATION_VERSION", "1.0"))
    fingerprint_version: str = field(default_factory=lambda: _env("OBSERVATION_FINGERPRINT_VERSION", "1.0"))
    engine_version: str = field(default_factory=lambda: _env("OBSERVATION_ENGINE_VERSION", "1.0"))


@dataclass(frozen=True)
class Settings:
    database: DatabaseSettings = field(default_factory=DatabaseSettings)
    versions: VersionSettings = field(default_factory=VersionSettings)


def load_settings() -> Settings:
    return Settings(database=DatabaseSettings(), versions=VersionSettings())
