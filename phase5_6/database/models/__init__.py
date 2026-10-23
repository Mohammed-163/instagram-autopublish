from database.models.base import Base

# Phase 1 — existing operational models
from database.models.design import Design
from database.models.history import PublishingHistory
from database.models.media import Media
from database.models.metric import Metric
from database.models.post import Post
from database.models.schedule import PublishingSchedule
from database.models.topic import Topic

# Structural foundation for Phase 2 (Learning & Intelligence Layer).
# These tables exist so the future engines don't require a schema redesign;
# no engine writes to them yet.
from database.models.audit_log import AuditLog
from database.models.confidence_score import ConfidenceScore
from database.models.decision_log import DecisionLog
from database.models.engine_health import EngineHealth
from database.models.event_log import EventLog
from database.models.experiment import Experiment
from database.models.explainability_note import ExplainabilityNote
from database.models.failure import Failure
from database.models.feature import Feature
from database.models.hypothesis import Hypothesis
from database.models.knowledge_rule import KnowledgeRule
from database.models.knowledge_version import KnowledgeVersion
from database.models.memory_entry import MemoryEntry
from database.models.model_version import ModelVersion
from database.models.notification import Notification
from database.models.prompt_version import PromptVersion
from database.models.quality_result import QualityResult
from database.models.rule_lifecycle_event import RuleLifecycleEvent
from database.models.score import Score
from database.models.strategy_history import StrategyHistory
from database.models.system_setting import SystemSetting
from database.models.weekly_plan import WeeklyPlan

# Phase 4 (Part 1) — Strategy & Planning Layer (planning only, no execution)
from database.models.hook_pattern import HookPattern
from database.models.hook_statistic import HookStatistic
from database.models.strategy_candidate import StrategyCandidate
from database.models.weekly_strategy_version import WeeklyStrategyVersion

# Phase 4 (Part 2) — Hook Structure Learning & Opportunity Discovery Foundation
from database.models.hook_structure import HookStructure
from database.models.hook_feature_value import HookFeatureValue
from database.models.hook_feature_statistic import HookFeatureStatistic
from database.models.knowledge_coverage_snapshot import KnowledgeCoverageSnapshot

# Phase C — Opportunity Intelligence Layer
from database.models.opportunity import Opportunity, OpportunityTransition

# Phase 5 (Part 1) — Decision Layer Foundation
from database.models.decision_candidate import DecisionCandidateRecord
# Phase 5 (Part 2) — Decision Lifecycle Completion
from database.models.decision_candidate import DecisionTransition

# Phase 6 — Execution Layer
from database.models.execution import ExecutionRecord, ExecutionTransition

__all__ = [
    "Base",
    # Phase 1
    "Topic",
    "Post",
    "Design",
    "Media",
    "PublishingSchedule",
    "PublishingHistory",
    "Metric",
    # Phase 2 foundation
    "AuditLog",
    "Feature",
    "Score",
    "KnowledgeVersion",
    "KnowledgeRule",
    "RuleLifecycleEvent",
    "Hypothesis",
    "Experiment",
    "MemoryEntry",
    "WeeklyPlan",
    "StrategyHistory",
    "DecisionLog",
    "ConfidenceScore",
    "QualityResult",
    "EngineHealth",
    "Notification",
    "EventLog",
    "SystemSetting",
    "PromptVersion",
    "ModelVersion",
    "Failure",
    "ExplainabilityNote",
    # Phase 4 Part 1
    "HookPattern",
    "HookStatistic",
    "StrategyCandidate",
    "WeeklyStrategyVersion",
    # Phase 4 Part 2
    "HookStructure",
    "HookFeatureValue",
    "HookFeatureStatistic",
    "KnowledgeCoverageSnapshot",
    # Phase C
    "Opportunity",
    "OpportunityTransition",
    # Phase 5 Part 1
    "DecisionCandidateRecord",
    # Phase 5 Part 2
    "DecisionTransition",
    # Phase 6
    "ExecutionRecord",
    "ExecutionTransition",
]
