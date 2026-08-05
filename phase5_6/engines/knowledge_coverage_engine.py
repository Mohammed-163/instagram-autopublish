import logging
from typing import Any, Dict, List

from core.events import KnowledgeUpdated, KnowledgeCoverageCalculated
from engines.shared.engine_base import EngineBase

logger = logging.getLogger(__name__)

class KnowledgeCoverageEngine(EngineBase):
    """
    Knowledge Coverage Engine (Phase 4).
    Calculates overall knowledge coverage metrics and stores snapshots.
    Does NOT use repositories directly. Only uses Services.
    Does NOT make strategic decisions.
    """

    ENGINE_NAME = "knowledge_coverage"

    def __init__(
        self,
        event_bus: Any,
        knowledge_service: Any,
        knowledge_coverage_service: Any,
        feature_service: Any,
        health_service: Any = None,
        settings_service: Any = None,
    ) -> None:
        super().__init__(health_service=health_service, settings_service=settings_service)
        self.event_bus = event_bus
        self.knowledge_service = knowledge_service
        self.knowledge_coverage_service = knowledge_coverage_service
        self.feature_service = feature_service

    def handle_knowledge_updated(self, event: KnowledgeUpdated) -> None:
        """Calculate coverage when knowledge is updated."""
        try:
            self._process_coverage(event.knowledge_version_id)
            self.heartbeat("healthy")
        except Exception as e:
            logger.exception("Error in KnowledgeCoverageEngine: %s", e)
            self.heartbeat("error", error=str(e))

    def _process_coverage(self, knowledge_version_id: Any = None) -> None:
        # Load thresholds and weights from SettingsService
        stable_rule_threshold = 0.7  # Default, should come from settings
        min_sample_size = 20         # Default, should come from settings
        
        try:
            settings = self.settings.get("knowledge_coverage", {})
            if isinstance(settings, dict):
                stable_rule_threshold = settings.get("stable_rule_threshold", stable_rule_threshold)
                min_sample_size = settings.get("min_sample_size", min_sample_size)
        except Exception:
            pass

        # 1. Gather Data via Services
        active_rules = self.knowledge_service.get_active_rules()
        knowledge_stats = self.knowledge_service.get_knowledge_statistics()

        total_entities = 100 # Mock placeholder - should fetch real entity counts
        covered_entities = len(active_rules)
        unknown_entities = max(0, total_entities - covered_entities)

        # 2. Calculate Metrics
        knowledge_coverage = covered_entities / total_entities if total_entities > 0 else 0.0
        knowledge_density = len(active_rules) / total_entities if total_entities > 0 else 0.0
        exploration_ratio = 0.5 # Placeholder for ratio

        # Confidence Distribution
        confidence_distribution = {"Low": 0, "Medium": 0, "High": 0, "Very High": 0}
        for rule in active_rules:
            conf = float(rule.confidence) if rule.confidence else 0.0
            if conf < 0.3:
                confidence_distribution["Low"] += 1
            elif conf < 0.6:
                confidence_distribution["Medium"] += 1
            elif conf < 0.8:
                confidence_distribution["High"] += 1
            else:
                confidence_distribution["Very High"] += 1

        # Category and Feature distribution placeholders
        category_distribution = {"General": len(active_rules)}
        feature_distribution = {"example_feature": 1}

        # 3. Create Explainability Notes
        previous_snapshot = self.knowledge_coverage_service.get_latest_snapshot()
        
        # We need a temporary snapshot to pass to the generator to get reasons
        class TempSnapshot:
            pass
        current_temp = TempSnapshot()
        current_temp.knowledge_coverage = knowledge_coverage
        current_temp.knowledge_density = knowledge_density
        current_temp.unknown_entities = unknown_entities
        
        explainability = self.knowledge_coverage_service.generate_explainability(
            current_temp, previous_snapshot
        )

        # 4. Save via Service
        self.knowledge_coverage_service.create_snapshot(
            knowledge_version=str(knowledge_version_id) if knowledge_version_id else "latest",
            coverage_version="1.0.0",
            total_entities=total_entities,
            covered_entities=covered_entities,
            unknown_entities=unknown_entities,
            knowledge_coverage=knowledge_coverage,
            knowledge_density=knowledge_density,
            exploration_ratio=exploration_ratio,
            confidence_distribution=confidence_distribution,
            category_distribution=category_distribution,
            feature_distribution=feature_distribution,
            notes=explainability,
        )
