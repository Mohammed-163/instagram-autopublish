from __future__ import annotations
import logging
from typing import List, Optional, Any, Dict

from database.models import DecisionLog
from core.container import container

logger = logging.getLogger(__name__)


class DecisionService:
    def __init__(self, decision_logs_repository=None) -> None:
        self.decision_logs_repository = decision_logs_repository or container.resolve("decision_logs_repository")

    def log_decision(
        self,
        decision_type: str,
        context: Dict[str, Any],
        chosen_action: Dict[str, Any],
        reasoning: str,
        confidence: float,
        post_id: Optional[Any] = None,
    ) -> DecisionLog:
        return self.decision_logs_repository.create(
            decision_type=decision_type,
            context=context,
            chosen_action=chosen_action,
            reasoning=reasoning,
            confidence=confidence,
            related_post_id=post_id,
        )

    def get_decisions_for_post(self, post_id: Any) -> List[DecisionLog]:
        return self.decision_logs_repository.list_for_post(post_id)

    def get_decision_statistics(self, days: int = 30) -> Dict[str, Any]:
        decisions = self.decision_logs_repository.list_all()
        stats: Dict[str, Any] = {"total": len(decisions), "avg_confidence": 0, "by_type": {}}
        if not decisions:
            return stats

        total_conf = 0
        for d in decisions:
            total_conf += d.confidence or 0
            stats["by_type"][d.decision_type] = stats["by_type"].get(d.decision_type, 0) + 1

        stats["avg_confidence"] = total_conf / len(decisions)
        return stats

    def get_decisions_by_type(self, decision_type: str, limit: int = 100) -> List[DecisionLog]:
        return self.decision_logs_repository.list_by_type(decision_type, limit=limit)

    def log_engine_decision(
        self,
        decision_type: str,
        reasoning: str,
        evidence: Dict[str, Any],
        confidence_level: float,
    ) -> None:
        """
        Persist a decision produced by DecisionEngine.
        Uses a flat signature matching what the engine provides after experiment evaluation.
        """
        try:
            self.decision_logs_repository.create(
                decision_type=decision_type,
                reasoning=reasoning,
                evidence=evidence,
                confidence_level=confidence_level,
            )
            logger.debug("[DecisionService] Decision logged: type=%s", decision_type)
        except Exception:
            logger.exception("[DecisionService] Failed to persist decision")


decision_service = DecisionService()
