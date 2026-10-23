"""
EngineSettingsReader
====================
Thin wrapper around SettingsService that provides typed, defaulted access to
every configurable value used by the pipeline engines.

Design decisions
----------------
- All setting keys are declared as class-level constants so they are greppable
  and refactor-safe (no magic strings scattered across engines).
- Every getter has an explicit Python-typed default, so the system works
  correctly even before the database is seeded with settings rows.
- The reader is injected into engines via constructor, not imported as a
  module-level singleton, so unit tests can supply a fake SettingsService
  with zero boilerplate.
"""
from __future__ import annotations

from typing import Any, List, Optional


class EngineSettingsReader:
    """Read engine configuration from SettingsService with typed defaults."""

    # ------------------------------------------------------------------ keys
    # Scoring weights (must sum to 1.0)
    KEY_SCORE_WEIGHT_ENGAGEMENT = "scoring.weight.engagement"
    KEY_SCORE_WEIGHT_RETENTION = "scoring.weight.retention"
    KEY_SCORE_WEIGHT_VIRALITY = "scoring.weight.virality"
    KEY_SCORE_WEIGHT_READABILITY = "scoring.weight.readability"
    KEY_SCORE_WEIGHT_VISUAL = "scoring.weight.visual"
    # Pre-publish content-quality weights (FeatureScoringEngine). Kept separate
    # from engagement/retention/virality above, which describe post-publish
    # performance dimensions (ObjectiveEngine/PerformanceEvaluationEngine).
    KEY_SCORE_WEIGHT_HOOK = "scoring.weight.hook"
    KEY_SCORE_WEIGHT_DENSITY = "scoring.weight.density"

    # Scoring – readability thresholds
    KEY_READABILITY_OPTIMAL_MIN = "scoring.readability.optimal_min"
    KEY_READABILITY_OPTIMAL_MAX = "scoring.readability.optimal_max"
    KEY_READABILITY_SCORE_OPTIMAL = "scoring.readability.score_optimal"
    KEY_READABILITY_SCORE_SHORT = "scoring.readability.score_short"
    KEY_READABILITY_SCORE_LONG = "scoring.readability.score_long"

    # Scoring – metric multipliers
    KEY_MULTIPLIER_COMMENTS = "scoring.multiplier.comments"
    KEY_MULTIPLIER_SAVES_ENGAGEMENT = "scoring.multiplier.saves_engagement"
    KEY_MULTIPLIER_SAVES_RETENTION = "scoring.multiplier.saves_retention"
    KEY_MULTIPLIER_SHARES = "scoring.multiplier.shares"

    # Pattern discovery thresholds
    KEY_PATTERN_MIN_OVERALL_SCORE = "pattern.min_overall_score"
    KEY_PATTERN_MIN_READABILITY_SCORE = "pattern.min_readability_score"
    KEY_PATTERN_CONFIDENCE_BOOST = "pattern.confidence_boost"

    # Confidence engine
    KEY_CONFIDENCE_MIN_SAMPLE_SIZE = "min_sample_size"
    KEY_CONFIDENCE_BASE = "base_confidence"
    KEY_CONFIDENCE_SUCCESS_WEIGHT = "success_weight"

    # Hypothesis engine
    KEY_HYPOTHESIS_MIN_CONFIDENCE = "hypothesis.min_confidence_threshold"
    KEY_HYPOTHESIS_ENGAGEMENT_INCREASE_PCT = "hypothesis.expected_engagement_increase_pct"
    KEY_HYPOTHESIS_MIN_SAMPLE_SIZE = "hypothesis.min_sample_size"

    # Decision engine
    KEY_DECISION_CONFIDENCE_THRESHOLD = "decision.confidence_threshold"
    KEY_DECISION_CONFIDENCE_LEVEL = "decision.confidence_level"

    # Weekly planning
    KEY_PLANNING_MIN_POSTS = "planning.min_posts"
    KEY_PLANNING_DIVERSITY_INDEX = "planning.diversity_index"
    KEY_PLANNING_POSTING_SLOTS = "planning.posting_slots"
    KEY_PLANNING_RECOMMENDED_FORMATS = "planning.recommended_formats"

    # Hook statistics (Phase 4 Part 1)
    KEY_HOOK_MIN_SAMPLE_SIZE = "hook.min_sample_size"
    KEY_HOOK_HIGH_SUCCESS_THRESHOLD = "hook.high_success_threshold"
    KEY_HOOK_MEDIUM_SUCCESS_THRESHOLD = "hook.medium_success_threshold"
    KEY_HOOK_RULE_CONFIDENCE_THRESHOLD = "hook.rule_confidence_threshold"

    # Strategy planning (Phase 4 Part 1)
    KEY_STRATEGY_MIN_POSTS = "strategy.min_posts"
    KEY_STRATEGY_EXPLORATION_RATIO = "strategy.exploration_ratio"
    KEY_STRATEGY_DEFAULT_CATEGORIES = "strategy.default_categories"
    KEY_STRATEGY_FALLBACK_HOOK_TYPES = "strategy.fallback_hook_types"

    # ------------------------------------------------------------------ defaults
    _DEFAULTS: dict = {
        KEY_SCORE_WEIGHT_ENGAGEMENT: 0.35,
        KEY_SCORE_WEIGHT_RETENTION: 0.20,
        KEY_SCORE_WEIGHT_VIRALITY: 0.20,
        KEY_SCORE_WEIGHT_READABILITY: 0.15,
        KEY_SCORE_WEIGHT_VISUAL: 0.10,
        KEY_SCORE_WEIGHT_HOOK: 0.35,
        KEY_SCORE_WEIGHT_DENSITY: 0.15,
        KEY_READABILITY_OPTIMAL_MIN: 100.0,
        KEY_READABILITY_OPTIMAL_MAX: 300.0,
        KEY_READABILITY_SCORE_OPTIMAL: 0.9,
        KEY_READABILITY_SCORE_SHORT: 0.6,
        KEY_READABILITY_SCORE_LONG: 0.7,
        KEY_MULTIPLIER_COMMENTS: 2.0,
        KEY_MULTIPLIER_SAVES_ENGAGEMENT: 3.0,
        KEY_MULTIPLIER_SAVES_RETENTION: 10.0,
        KEY_MULTIPLIER_SHARES: 15.0,
        KEY_PATTERN_MIN_OVERALL_SCORE: 0.5,
        KEY_PATTERN_MIN_READABILITY_SCORE: 0.8,
        KEY_PATTERN_CONFIDENCE_BOOST: 1.2,
        KEY_CONFIDENCE_MIN_SAMPLE_SIZE: 5.0,
        KEY_CONFIDENCE_BASE: 0.5,
        KEY_CONFIDENCE_SUCCESS_WEIGHT: 0.1,
        KEY_HYPOTHESIS_MIN_CONFIDENCE: 0.4,
        KEY_HYPOTHESIS_ENGAGEMENT_INCREASE_PCT: 15.0,
        KEY_HYPOTHESIS_MIN_SAMPLE_SIZE: 20,
        KEY_DECISION_CONFIDENCE_THRESHOLD: 0.5,
        KEY_DECISION_CONFIDENCE_LEVEL: 0.88,
        KEY_PLANNING_MIN_POSTS: 7,
        KEY_PLANNING_DIVERSITY_INDEX: 0.85,
        KEY_PLANNING_POSTING_SLOTS: ["09:00 UTC", "14:00 UTC", "19:00 UTC"],
        KEY_PLANNING_RECOMMENDED_FORMATS: ["carousel", "reel", "single_image"],
        KEY_HOOK_MIN_SAMPLE_SIZE: 5,
        KEY_HOOK_HIGH_SUCCESS_THRESHOLD: 0.7,
        KEY_HOOK_MEDIUM_SUCCESS_THRESHOLD: 0.4,
        KEY_HOOK_RULE_CONFIDENCE_THRESHOLD: 0.6,
        KEY_STRATEGY_MIN_POSTS: 7,
        KEY_STRATEGY_EXPLORATION_RATIO: 0.2,
        KEY_STRATEGY_DEFAULT_CATEGORIES: ["Science", "Psychology", "History", "Body"],
        KEY_STRATEGY_FALLBACK_HOOK_TYPES: ["curiosity", "question", "number", "myth"],
    }

    def __init__(self, settings_service: Any) -> None:
        self._svc = settings_service

    # ------------------------------------------------------------------ helpers
    def get_float(self, key: str) -> float:
        """Return a float setting, falling back to the declared default."""
        default = float(self._DEFAULTS.get(key, 0.0))
        try:
            val = self._svc.get(key, default)
            return float(val)
        except Exception:
            return default

    def get_int(self, key: str) -> int:
        default = int(self._DEFAULTS.get(key, 0))
        try:
            val = self._svc.get(key, default)
            return int(val)
        except Exception:
            return default

    def get_list(self, key: str) -> List[Any]:
        default = self._DEFAULTS.get(key, [])
        try:
            val = self._svc.get(key, default)
            if isinstance(val, list):
                return val
            return default
        except Exception:
            return list(default)

    def get_str(self, key: str) -> str:
        default = str(self._DEFAULTS.get(key, ""))
        try:
            val = self._svc.get(key, default)
            return str(val)
        except Exception:
            return default

    # ------------------------------------------------------------------ typed accessors
    # Scoring weights
    @property
    def score_weight_engagement(self) -> float:
        return self.get_float(self.KEY_SCORE_WEIGHT_ENGAGEMENT)

    @property
    def score_weight_retention(self) -> float:
        return self.get_float(self.KEY_SCORE_WEIGHT_RETENTION)

    @property
    def score_weight_virality(self) -> float:
        return self.get_float(self.KEY_SCORE_WEIGHT_VIRALITY)

    @property
    def score_weight_readability(self) -> float:
        return self.get_float(self.KEY_SCORE_WEIGHT_READABILITY)

    @property
    def score_weight_visual(self) -> float:
        return self.get_float(self.KEY_SCORE_WEIGHT_VISUAL)

    @property
    def score_weight_hook(self) -> float:
        return self.get_float(self.KEY_SCORE_WEIGHT_HOOK)

    @property
    def score_weight_density(self) -> float:
        return self.get_float(self.KEY_SCORE_WEIGHT_DENSITY)

    # Readability thresholds
    @property
    def readability_optimal_min(self) -> float:
        return self.get_float(self.KEY_READABILITY_OPTIMAL_MIN)

    @property
    def readability_optimal_max(self) -> float:
        return self.get_float(self.KEY_READABILITY_OPTIMAL_MAX)

    @property
    def readability_score_optimal(self) -> float:
        return self.get_float(self.KEY_READABILITY_SCORE_OPTIMAL)

    @property
    def readability_score_short(self) -> float:
        return self.get_float(self.KEY_READABILITY_SCORE_SHORT)

    @property
    def readability_score_long(self) -> float:
        return self.get_float(self.KEY_READABILITY_SCORE_LONG)

    # Multipliers
    @property
    def multiplier_comments(self) -> float:
        return self.get_float(self.KEY_MULTIPLIER_COMMENTS)

    @property
    def multiplier_saves_engagement(self) -> float:
        return self.get_float(self.KEY_MULTIPLIER_SAVES_ENGAGEMENT)

    @property
    def multiplier_saves_retention(self) -> float:
        return self.get_float(self.KEY_MULTIPLIER_SAVES_RETENTION)

    @property
    def multiplier_shares(self) -> float:
        return self.get_float(self.KEY_MULTIPLIER_SHARES)

    # Pattern thresholds
    @property
    def pattern_min_overall_score(self) -> float:
        return self.get_float(self.KEY_PATTERN_MIN_OVERALL_SCORE)

    @property
    def pattern_min_readability_score(self) -> float:
        return self.get_float(self.KEY_PATTERN_MIN_READABILITY_SCORE)

    @property
    def pattern_confidence_boost(self) -> float:
        return self.get_float(self.KEY_PATTERN_CONFIDENCE_BOOST)

    # Confidence thresholds
    @property
    def confidence_min_sample_size(self) -> float:
        return self.get_float(self.KEY_CONFIDENCE_MIN_SAMPLE_SIZE)

    @property
    def confidence_base(self) -> float:
        return self.get_float(self.KEY_CONFIDENCE_BASE)

    @property
    def confidence_success_weight(self) -> float:
        return self.get_float(self.KEY_CONFIDENCE_SUCCESS_WEIGHT)

    # Hypothesis thresholds
    @property
    def hypothesis_min_confidence(self) -> float:
        return self.get_float(self.KEY_HYPOTHESIS_MIN_CONFIDENCE)

    @property
    def hypothesis_expected_engagement_increase_pct(self) -> float:
        return self.get_float(self.KEY_HYPOTHESIS_ENGAGEMENT_INCREASE_PCT)

    @property
    def hypothesis_min_sample_size(self) -> int:
        return self.get_int(self.KEY_HYPOTHESIS_MIN_SAMPLE_SIZE)

    # Decision thresholds
    @property
    def decision_confidence_threshold(self) -> float:
        return self.get_float(self.KEY_DECISION_CONFIDENCE_THRESHOLD)

    @property
    def decision_confidence_level(self) -> float:
        return self.get_float(self.KEY_DECISION_CONFIDENCE_LEVEL)

    # Planning parameters
    @property
    def planning_min_posts(self) -> int:
        return self.get_int(self.KEY_PLANNING_MIN_POSTS)

    @property
    def planning_diversity_index(self) -> float:
        return self.get_float(self.KEY_PLANNING_DIVERSITY_INDEX)

    @property
    def planning_posting_slots(self) -> List[str]:
        return self.get_list(self.KEY_PLANNING_POSTING_SLOTS)

    @property
    def planning_recommended_formats(self) -> List[str]:
        return self.get_list(self.KEY_PLANNING_RECOMMENDED_FORMATS)

    # Hook statistics
    @property
    def hook_min_sample_size(self) -> int:
        return self.get_int(self.KEY_HOOK_MIN_SAMPLE_SIZE)

    @property
    def hook_high_success_threshold(self) -> float:
        return self.get_float(self.KEY_HOOK_HIGH_SUCCESS_THRESHOLD)

    @property
    def hook_medium_success_threshold(self) -> float:
        return self.get_float(self.KEY_HOOK_MEDIUM_SUCCESS_THRESHOLD)

    @property
    def hook_rule_confidence_threshold(self) -> float:
        return self.get_float(self.KEY_HOOK_RULE_CONFIDENCE_THRESHOLD)

    # Strategy planning
    @property
    def strategy_min_posts(self) -> int:
        return self.get_int(self.KEY_STRATEGY_MIN_POSTS)

    @property
    def strategy_exploration_ratio(self) -> float:
        return self.get_float(self.KEY_STRATEGY_EXPLORATION_RATIO)

    @property
    def strategy_default_categories(self) -> List[str]:
        return self.get_list(self.KEY_STRATEGY_DEFAULT_CATEGORIES)

    @property
    def strategy_fallback_hook_types(self) -> List[str]:
        return self.get_list(self.KEY_STRATEGY_FALLBACK_HOOK_TYPES)
