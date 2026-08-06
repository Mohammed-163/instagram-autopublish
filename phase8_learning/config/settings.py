"""
Settings for the Learning Layer, read from environment variables.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value is not None else default


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    return float(value) if value is not None else default


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value is not None else default


def _resolve_db_url() -> str:
    # Priority: LEARNING_LAYER_DATABASE_URL → KCL_DATABASE_URL → P10_DATABASE_URL
    #           → DATABASE_URL → derived from SUPABASE_URL + SUPABASE_SECRET_KEY
    for var in ("LEARNING_LAYER_DATABASE_URL", "KCL_DATABASE_URL", "P10_DATABASE_URL"):
        v = os.environ.get(var, "")
        if v:
            return v
    _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from operational.db_config import resolve_database_url
    return resolve_database_url("LEARNING_LAYER_DATABASE_URL", "sqlite:///./phase8_learning_layer.db")


@dataclass(frozen=True)
class Settings:
    database_url: str
    fingerprint_version: str
    engine_version: str
    schema_version: str
    min_confidence_threshold: float
    min_sample_size: int
    min_consistency_threshold: float

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            database_url=_resolve_db_url(),
            fingerprint_version=_env_str("LEARNING_LAYER_FINGERPRINT_VERSION", "1.0.0"),
            engine_version=_env_str("LEARNING_LAYER_ENGINE_VERSION", "1.0.0"),
            schema_version=_env_str("LEARNING_LAYER_SCHEMA_VERSION", "1.0.0"),
            min_confidence_threshold=_env_float("LEARNING_LAYER_MIN_CONFIDENCE", 0.5),
            min_sample_size=_env_int("LEARNING_LAYER_MIN_SAMPLE_SIZE", 2),
            min_consistency_threshold=_env_float("LEARNING_LAYER_MIN_CONSISTENCY", 0.5),
        )
