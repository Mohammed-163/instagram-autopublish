"""
Centralized configuration for Phase10-Intelligence-Core.
All business constants and settings live here with env-var overrides.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field


def _env_float(name: str, default: float) -> float:
    val = os.environ.get(name)
    return float(val) if val is not None else default

def _env_int(name: str, default: int) -> int:
    val = os.environ.get(name)
    return int(val) if val is not None else default

def _env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)

def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")

def _resolve_p10_db_url() -> str:
    # Priority: LEARNING_LAYER_DATABASE_URL → KCL_DATABASE_URL → P10_DATABASE_URL
    #           → DATABASE_URL → derived from SUPABASE_URL + SUPABASE_SECRET_KEY
    for var in ("LEARNING_LAYER_DATABASE_URL", "KCL_DATABASE_URL", "P10_DATABASE_URL"):
        v = os.environ.get(var, "")
        if v: return v
    _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from operational.db_config import resolve_database_url
    return resolve_database_url("P10_DATABASE_URL", "sqlite:///phase10_intelligence_core.db")


@dataclass(frozen=True)
class Settings:
    """Immutable, environment-overridable settings container."""

    # --- Versioning ---
    schema_version: str = field(default_factory=lambda: _env_str("P10_SCHEMA_VERSION", "1.0.0"))
    policy_version: str = field(default_factory=lambda: _env_str("P10_POLICY_VERSION", "1.0.0"))
    strategy_version: str = field(default_factory=lambda: _env_str("P10_STRATEGY_VERSION", "1.0.0"))

    # --- Database ---
    database_url: str = field(default_factory=lambda: _resolve_p10_db_url())
    sql_echo: bool = field(default_factory=lambda: _env_bool("P10_SQL_ECHO", False))

    # --- Confidence calibration ---
    min_confidence_threshold: float = field(default_factory=lambda: _env_float("P10_MIN_CONFIDENCE_THRESHOLD", 0.55))
    high_confidence_threshold: float = field(default_factory=lambda: _env_float("P10_HIGH_CONFIDENCE_THRESHOLD", 0.80))
    calibration_smoothing_factor: float = field(default_factory=lambda: _env_float("P10_CALIBRATION_SMOOTHING_FACTOR", 0.10))

    # --- Governance ---
    governance_max_daily_decisions: int = field(default_factory=lambda: _env_int("P10_GOVERNANCE_MAX_DAILY_DECISIONS", 10))
    governance_require_approval_above: float = field(default_factory=lambda: _env_float("P10_GOVERNANCE_APPROVAL_THRESHOLD", 0.90))
    governance_max_risk_score: float = field(default_factory=lambda: _env_float("P10_GOVERNANCE_MAX_RISK_SCORE", 0.80))
    governance_required_approvals: int = field(default_factory=lambda: _env_int("P10_GOVERNANCE_REQUIRED_APPROVALS", 1))

    # --- Opportunity ---
    opportunity_min_score: float = field(default_factory=lambda: _env_float("P10_OPPORTUNITY_MIN_SCORE", 0.50))
    opportunity_ranking_weight_confidence: float = field(default_factory=lambda: _env_float("P10_OPPORTUNITY_RANKING_WEIGHT_CONFIDENCE", 0.40))
    opportunity_ranking_weight_novelty: float = field(default_factory=lambda: _env_float("P10_OPPORTUNITY_RANKING_WEIGHT_NOVELTY", 0.30))
    opportunity_ranking_weight_coverage_gap: float = field(default_factory=lambda: _env_float("P10_OPPORTUNITY_RANKING_WEIGHT_COVERAGE_GAP", 0.30))
    opportunity_ranking_weight_impact: float = field(default_factory=lambda: _env_float("P10_OPPORTUNITY_RANKING_WEIGHT_IMPACT", 0.30))
    opportunity_max_per_cycle: int = field(default_factory=lambda: _env_int("P10_OPPORTUNITY_MAX_PER_CYCLE", 5))
    opportunity_min_validation_evidence: int = field(default_factory=lambda: _env_int("P10_OPPORTUNITY_MIN_VALIDATION_EVIDENCE", 3))
    opportunity_validation_min_evidence_count: int = field(default_factory=lambda: _env_int("P10_OPPORTUNITY_MIN_EVIDENCE_COUNT", 2))

    # --- Strategy optimization ---
    strategy_min_evidence_for_evolution: int = field(default_factory=lambda: _env_int("P10_STRATEGY_MIN_EVIDENCE", 5))
    strategy_max_active_experiments: int = field(default_factory=lambda: _env_int("P10_STRATEGY_MAX_EXPERIMENTS", 3))
    strategy_confidence_band: float = field(default_factory=lambda: _env_float("P10_STRATEGY_CONFIDENCE_BAND", 0.10))
    strategy_elite_retention: float = field(default_factory=lambda: _env_float("P10_STRATEGY_ELITE_RETENTION", 0.2))
    strategy_mutation_rate: float = field(default_factory=lambda: _env_float("P10_STRATEGY_MUTATION_RATE", 0.1))
    strategy_optimization_min_improvement: float = field(default_factory=lambda: _env_float("P10_STRATEGY_MIN_IMPROVEMENT", 0.05))

    # --- Rule evolution ---
    rule_min_support: float = field(default_factory=lambda: _env_float("P10_RULE_MIN_SUPPORT", 0.30))
    rule_min_confidence: float = field(default_factory=lambda: _env_float("P10_RULE_MIN_CONFIDENCE", 0.60))
    rule_max_age_days: int = field(default_factory=lambda: _env_int("P10_RULE_MAX_AGE_DAYS", 90))
    rule_confidence_decay: float = field(default_factory=lambda: _env_float("P10_RULE_CONFIDENCE_DECAY", 0.05))
    rule_evolution_max_rules: int = field(default_factory=lambda: _env_int("P10_RULE_EVOLUTION_MAX_RULES", 100))

    # --- Experiments ---
    experiment_max_concurrent: int = field(default_factory=lambda: _env_int("P10_EXPERIMENT_MAX_CONCURRENT", 3))
    experiment_min_sample_size: int = field(default_factory=lambda: _env_int("P10_EXPERIMENT_MIN_SAMPLE_SIZE", 10))
    experiment_significance_threshold: float = field(default_factory=lambda: _env_float("P10_EXPERIMENT_SIGNIFICANCE", 0.05))

    # --- Hypotheses ---
    hypothesis_expiry_cycles: int = field(default_factory=lambda: _env_int("P10_HYPOTHESIS_EXPIRY_CYCLES", 30))
    hypothesis_max_active: int = field(default_factory=lambda: _env_int("P10_HYPOTHESIS_MAX_ACTIVE", 20))

    # --- Planning ---
    planning_horizon_cycles: int = field(default_factory=lambda: _env_int("P10_PLANNING_HORIZON_CYCLES", 7))
    planning_risk_tolerance: float = field(default_factory=lambda: _env_float("P10_PLANNING_RISK_TOLERANCE", 0.3))

    # --- Feedback ---
    feedback_loop_learning_rate: float = field(default_factory=lambda: _env_float("P10_FEEDBACK_LEARNING_RATE", 0.1))

    # --- Knowledge ---
    knowledge_utilization_min_relevance: float = field(default_factory=lambda: _env_float("P10_KNOWLEDGE_MIN_RELEVANCE", 0.5))

    # --- Memory ---
    memory_max_entries: int = field(default_factory=lambda: _env_int("P10_MEMORY_MAX_ENTRIES", 1000))
    memory_retention_days: int = field(default_factory=lambda: _env_int("P10_MEMORY_RETENTION_DAYS", 365))
    memory_retention_limit: int = field(default_factory=lambda: _env_int("P10_MEMORY_RETENTION_LIMIT", 1000))

    # --- Replay / Audit ---
    replay_strict_mode: bool = field(default_factory=lambda: _env_bool("P10_REPLAY_STRICT_MODE", True))

    # --- Self-improvement ---
    self_improvement_min_sample_size: int = field(default_factory=lambda: _env_int("P10_SELF_IMPROVEMENT_MIN_SAMPLE", 10))
    self_improvement_review_window: int = field(default_factory=lambda: _env_int("P10_SELF_IMPROVEMENT_REVIEW_WINDOW", 7))


def get_settings() -> Settings:
    return Settings()
