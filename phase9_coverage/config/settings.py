"""
Environment-driven configuration for the Knowledge Coverage Layer.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_float(name: str, default: float) -> float:
    return float(os.environ.get(name, str(default)))


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


def _resolve_db_url() -> str:
    v = os.environ.get("KCL_DATABASE_URL", "")
    if v:
        return v
    v = os.environ.get("DATABASE_URL", "")
    if v:
        return v
    if os.environ.get("ALLOW_SQLITE_FALLBACK", "").lower() in ("1", "true", "yes"):
        return "sqlite+pysqlite:///./phase9_knowledge_coverage.db"
    _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from operational.db_config import resolve_database_url
    return resolve_database_url("KCL_DATABASE_URL", "sqlite+pysqlite:///./phase9_knowledge_coverage.db")


@dataclass(frozen=True)
class Settings:
    schema_version: str
    engine_version: str
    fingerprint_version: str
    coverage_version: str
    database_url: str

    topic_coverage_target: int = 5
    category_coverage_target: int = 3
    evidence_coverage_target: int = 10
    diversity_coverage_target: int = 8
    knowledge_density_target: float = 2.0
    relationship_coverage_target: int = 5

    min_evidence_items: int = 1
    weak_evidence_threshold: float = 0.4
    low_confidence_threshold: float = 0.5
    outdated_freshness_threshold: float = 0.3
    imbalanced_category_threshold: float = 0.4
    insufficient_diversity_threshold: float = 0.4
    low_density_threshold: float = 0.3
    sparse_relationship_threshold: float = 0.3

    @staticmethod
    def load() -> "Settings":
        return Settings(
            schema_version=_env("KCL_SCHEMA_VERSION", "1.0.0"),
            engine_version=_env("KCL_ENGINE_VERSION", "1.0.0"),
            fingerprint_version=_env("KCL_FINGERPRINT_VERSION", "1.0.0"),
            coverage_version=_env("KCL_COVERAGE_VERSION", "1.0.0"),
            database_url=_resolve_db_url(),
            topic_coverage_target=_env_int("KCL_TOPIC_COVERAGE_TARGET", 5),
            category_coverage_target=_env_int("KCL_CATEGORY_COVERAGE_TARGET", 3),
            evidence_coverage_target=_env_int("KCL_EVIDENCE_COVERAGE_TARGET", 10),
            diversity_coverage_target=_env_int("KCL_DIVERSITY_COVERAGE_TARGET", 8),
            knowledge_density_target=_env_float("KCL_KNOWLEDGE_DENSITY_TARGET", 2.0),
            relationship_coverage_target=_env_int("KCL_RELATIONSHIP_COVERAGE_TARGET", 5),
            min_evidence_items=_env_int("KCL_MIN_EVIDENCE_ITEMS", 1),
            weak_evidence_threshold=_env_float("KCL_WEAK_EVIDENCE_THRESHOLD", 0.4),
            low_confidence_threshold=_env_float("KCL_LOW_CONFIDENCE_THRESHOLD", 0.5),
            outdated_freshness_threshold=_env_float("KCL_OUTDATED_FRESHNESS_THRESHOLD", 0.3),
            imbalanced_category_threshold=_env_float("KCL_IMBALANCED_CATEGORY_THRESHOLD", 0.4),
            insufficient_diversity_threshold=_env_float("KCL_INSUFFICIENT_DIVERSITY_THRESHOLD", 0.4),
            low_density_threshold=_env_float("KCL_LOW_DENSITY_THRESHOLD", 0.3),
            sparse_relationship_threshold=_env_float("KCL_SPARSE_RELATIONSHIP_THRESHOLD", 0.3),
        )


def get_settings() -> Settings:
    return Settings.load()
