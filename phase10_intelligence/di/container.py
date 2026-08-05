"""
Minimal, explicit dependency-injection container.

No global state, no service locator magic: the Container simply wires
concrete repositories, services, and engines together from a Session,
Settings, and EventPublisher, and exposes them as attributes.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..config.settings import Settings, get_settings
from ..engines.governance_engine import GovernanceEngine
from ..engines.learning_engine import LearningEngine
from ..engines.opportunity_engine import OpportunityEngine
from ..engines.planning_engine import PlanningEngine
from ..engines.research_engine import ResearchEngine
from ..engines.strategy_engine import StrategyEngine
from ..events.publisher import EventPublisher, InMemoryEventPublisher
from ..repositories import (
    AuditRepository, CalibrationRepository, ExperimentRepository, FeedbackRepository,
    GovernanceRepository, HypothesisRepository, MemoryRepository, OpportunityRepository,
    PlanningRepository, ReplayRepository, RuleRepository, StrategyRepository,
)
from ..services import (
    AdaptivePlanningService, ConfidenceCalibrationService, DecisionFeedbackService,
    ExplainabilityService, ExperimentLifecycleService, GovernanceService,
    HypothesisLifecycleService, KnowledgeUtilizationService, LongTermMemoryService,
    OpportunityDiscoveryService, OpportunityRankingService, OpportunityValidationService,
    ReplayAuditService, RuleEvolutionService, SelfImprovementService,
    StrategyEvolutionService, StrategyOptimizationService,
)


class Container:
    """Wires repositories -> services -> engines for a single Session/Settings pair."""

    def __init__(self, session: Session, settings: Settings | None = None,
                 publisher: EventPublisher | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.publisher: EventPublisher = publisher or InMemoryEventPublisher()

        # Repositories (persistence only)
        self.opportunity_repository = OpportunityRepository(session)
        self.hypothesis_repository = HypothesisRepository(session)
        self.experiment_repository = ExperimentRepository(session)
        self.strategy_repository = StrategyRepository(session)
        self.rule_repository = RuleRepository(session)
        self.governance_repository = GovernanceRepository(session)
        self.calibration_repository = CalibrationRepository(session)
        self.planning_repository = PlanningRepository(session)
        self.memory_repository = MemoryRepository(session)
        self.feedback_repository = FeedbackRepository(session)
        self.replay_repository = ReplayRepository(session)
        self.audit_repository = AuditRepository(session)

        # Services (business logic only)
        self.opportunity_discovery_service = OpportunityDiscoveryService(
            self.opportunity_repository, self.settings, self.publisher)
        self.opportunity_validation_service = OpportunityValidationService(
            self.opportunity_repository, self.settings, self.publisher)
        self.opportunity_ranking_service = OpportunityRankingService(
            self.opportunity_repository, self.settings, self.publisher)
        self.hypothesis_lifecycle_service = HypothesisLifecycleService(
            self.hypothesis_repository, self.settings, self.publisher)
        self.experiment_lifecycle_service = ExperimentLifecycleService(
            self.experiment_repository, self.settings, self.publisher)
        self.strategy_evolution_service = StrategyEvolutionService(
            self.strategy_repository, self.settings, self.publisher)
        self.strategy_optimization_service = StrategyOptimizationService(
            self.strategy_repository, self.settings, self.publisher)
        self.rule_evolution_service = RuleEvolutionService(
            self.rule_repository, self.settings, self.publisher)
        self.governance_service = GovernanceService(
            self.governance_repository, self.settings, self.publisher)
        self.confidence_calibration_service = ConfidenceCalibrationService(
            self.calibration_repository, self.settings, self.publisher)
        self.adaptive_planning_service = AdaptivePlanningService(
            self.planning_repository, self.settings, self.publisher)
        self.long_term_memory_service = LongTermMemoryService(
            self.memory_repository, self.settings)
        self.knowledge_utilization_service = KnowledgeUtilizationService(
            self.memory_repository, self.settings)
        self.decision_feedback_service = DecisionFeedbackService(
            self.feedback_repository, self.settings, self.publisher)
        self.self_improvement_service = SelfImprovementService(
            self.feedback_repository, self.settings)
        self.replay_audit_service = ReplayAuditService(
            self.replay_repository, self.audit_repository, self.settings, self.publisher)
        self.explainability_service = ExplainabilityService()

        # Engines (orchestration only)
        self.opportunity_engine = OpportunityEngine(
            self.opportunity_discovery_service, self.opportunity_validation_service,
            self.opportunity_ranking_service)
        self.research_engine = ResearchEngine(
            self.hypothesis_lifecycle_service, self.experiment_lifecycle_service)
        self.strategy_engine = StrategyEngine(
            self.strategy_evolution_service, self.strategy_optimization_service)
        self.governance_engine = GovernanceEngine(
            self.governance_service, self.replay_audit_service)
        self.planning_engine = PlanningEngine(
            self.adaptive_planning_service, self.knowledge_utilization_service)
        self.learning_engine = LearningEngine(
            self.decision_feedback_service, self.confidence_calibration_service,
            self.self_improvement_service)
