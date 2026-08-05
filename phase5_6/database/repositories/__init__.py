"""
The only layer allowed to talk to the database.

Import ready-made singletons from here, e.g.:

    from database.repositories import posts_repository, metrics_repository

    post = posts_repository.get_by_id(post_id)
    metrics_repository.upsert_snapshot(post.id, "24h", datetime.utcnow(), reach=1000, saves=42)

Phase 1 operational repositories are listed first; the rest are the
structural-foundation repositories for the future Learning & Intelligence
Layer (Phase 2) — usable today, but nothing in Phase 1 writes to them yet
except database.migrate's own bookkeeping.
"""
# Phase 1 — operational repositories
from database.repositories.designs_repository import DesignsRepository, designs_repository
from database.repositories.history_repository import HistoryRepository, history_repository
from database.repositories.media_repository import MediaRepository, media_repository
from database.repositories.metrics_repository import MetricsRepository, metrics_repository
from database.repositories.posts_repository import PostsRepository, posts_repository
from database.repositories.schedule_repository import ScheduleRepository, schedule_repository
from database.repositories.topics_repository import TopicsRepository, topics_repository

# Phase 2 foundation — structural, unused by any Phase 1 script yet
from database.repositories.decisions_repository import (
    ConfidenceScoresRepository,
    DecisionLogsRepository,
    confidence_scores_repository,
    decision_logs_repository,
)
from database.repositories.events_repository import EventsRepository, events_repository
from database.repositories.explainability_repository import ExplainabilityRepository, explainability_repository
from database.repositories.failures_repository import FailuresRepository, failures_repository
from database.repositories.features_repository import FeaturesRepository, features_repository
from database.repositories.health_repository import EngineHealthRepository, engine_health_repository
from database.repositories.hook_repository import (
    HookPatternsRepository,
    HookStatisticsRepository,
    hook_patterns_repository,
    hook_statistics_repository,
)
from database.repositories.hook_structure_repository import (
    HookFeatureStatisticsRepository,
    HookFeatureValuesRepository,
    HookStructuresRepository,
    hook_feature_statistics_repository,
    hook_feature_values_repository,
    hook_structures_repository,
)
from database.repositories.hypotheses_repository import (
    ExperimentsRepository,
    HypothesesRepository,
    experiments_repository,
    hypotheses_repository,
)
from database.repositories.knowledge_repository import (
    KnowledgeRulesRepository,
    KnowledgeVersionsRepository,
    RuleLifecycleEventsRepository,
    knowledge_rules_repository,
    knowledge_versions_repository,
    rule_lifecycle_events_repository,
)
from database.repositories.memory_repository import MemoryRepository, memory_repository
from database.repositories.notifications_repository import NotificationsRepository, notifications_repository
from database.repositories.planning_repository import (
    StrategyHistoryRepository,
    WeeklyPlansRepository,
    strategy_history_repository,
    weekly_plans_repository,
)
from database.repositories.quality_repository import QualityResultsRepository, quality_results_repository
from database.repositories.scores_repository import ScoresRepository, scores_repository
from database.repositories.settings_repository import SettingsRepository, settings_repository
from database.repositories.strategy_repository import (
    StrategyCandidatesRepository,
    WeeklyStrategyVersionsRepository,
    strategy_candidates_repository,
    weekly_strategy_versions_repository,
)
from database.repositories.versions_repository import (
    ModelVersionsRepository,
    PromptVersionsRepository,
    model_versions_repository,
    prompt_versions_repository,
)
from database.repositories.knowledge_coverage_repository import (
    KnowledgeCoverageRepository,
    knowledge_coverage_repository,
)
from database.repositories.opportunity_repository import (
    OpportunityRepository,
    OpportunityTransitionRepository,
    opportunity_repository,
    opportunity_transition_repository,
)
# Phase 6 — Execution Layer
from database.repositories.execution_repository import ExecutionRepository, execution_repository

from database.repositories.decision_candidates_repository import (
    DecisionCandidatesRepository,
    decision_candidates_repository,
    DecisionTransitionsRepository,
    decision_transitions_repository,
)

__all__ = [
    # Phase 1
    "posts_repository", "PostsRepository",
    "topics_repository", "TopicsRepository",
    "designs_repository", "DesignsRepository",
    "media_repository", "MediaRepository",
    "schedule_repository", "ScheduleRepository",
    "history_repository", "HistoryRepository",
    "metrics_repository", "MetricsRepository",
    # Phase 2 foundation
    "features_repository", "FeaturesRepository",
    "scores_repository", "ScoresRepository",
    "knowledge_versions_repository", "KnowledgeVersionsRepository",
    "knowledge_rules_repository", "KnowledgeRulesRepository",
    "rule_lifecycle_events_repository", "RuleLifecycleEventsRepository",
    "hypotheses_repository", "HypothesesRepository",
    "experiments_repository", "ExperimentsRepository",
    "memory_repository", "MemoryRepository",
    "weekly_plans_repository", "WeeklyPlansRepository",
    "strategy_history_repository", "StrategyHistoryRepository",
    "decision_logs_repository", "DecisionLogsRepository",
    "confidence_scores_repository", "ConfidenceScoresRepository",
    "quality_results_repository", "QualityResultsRepository",
    "engine_health_repository", "EngineHealthRepository",
    "notifications_repository", "NotificationsRepository",
    "events_repository", "EventsRepository",
    "settings_repository", "SettingsRepository",
    "prompt_versions_repository", "PromptVersionsRepository",
    "model_versions_repository", "ModelVersionsRepository",
    "failures_repository", "FailuresRepository",
    "explainability_repository", "ExplainabilityRepository",
    # Phase 4 Part 1 — Strategy & Planning Layer
    "hook_patterns_repository", "HookPatternsRepository",
    "hook_statistics_repository", "HookStatisticsRepository",
    "weekly_strategy_versions_repository", "WeeklyStrategyVersionsRepository",
    "strategy_candidates_repository", "StrategyCandidatesRepository",
    # Phase 4 Part 2 — Hook Structure Learning
    "hook_structures_repository", "HookStructuresRepository",
    "hook_feature_values_repository", "HookFeatureValuesRepository",
    "hook_feature_statistics_repository", "HookFeatureStatisticsRepository",
    "knowledge_coverage_repository", "KnowledgeCoverageRepository",
    # Phase C
    "opportunity_repository", "OpportunityRepository",
    "opportunity_transition_repository", "OpportunityTransitionRepository",
    # Phase 5 Part 1 — Decision Layer Foundation
    "decision_candidates_repository", "DecisionCandidatesRepository",
    # Phase 5 Part 2 — Decision Lifecycle Completion
    "decision_transitions_repository", "DecisionTransitionsRepository",
    # Phase 6 — Execution Layer
    "execution_repository", "ExecutionRepository",
]
