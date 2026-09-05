from __future__ import annotations
import logging
from typing import List, Optional, Any, Dict

from database.models import Hypothesis, Experiment
from core.container import container
from core.events import ExperimentFinished

logger = logging.getLogger(__name__)


class ExperimentService:
    def __init__(self, hypotheses_repository=None, experiments_repository=None, event_bus=None) -> None:
        self.hypotheses_repository = hypotheses_repository or container.resolve("hypotheses_repository")
        self.experiments_repository = experiments_repository or container.resolve("experiments_repository")
        self.event_bus = event_bus or container.resolve("event_bus")

    def create_hypothesis(self, statement: str, rationale: Optional[str] = None) -> Hypothesis:
        return self.hypotheses_repository.create(statement=statement, rationale=rationale)

    def create_experiment(
        self,
        hypothesis_id: Any,
        name: str,
        variant_a: Optional[Dict[str, Any]] = None,
        variant_b: Optional[Dict[str, Any]] = None,
        winner: Optional[str] = None,
        status: str = "draft",
        variant_config: Optional[Dict[str, Any]] = None,
    ) -> Experiment:
        """
        Create an experiment record.
        Accepts both the legacy variant_config form and the A/B form used by
        ExperimentEngine (variant_a, variant_b, winner).
        """
        config = variant_config or {}
        if variant_a is not None:
            config["variant_a"] = variant_a
        if variant_b is not None:
            config["variant_b"] = variant_b
        if winner is not None:
            config["winner"] = winner
        return self.experiments_repository.create(
            hypothesis_id=hypothesis_id,
            name=name,
            variant_config=config,
            status=status,
        )

    def start_experiment(self, experiment_id: Any) -> Optional[Experiment]:
        exp = self.experiments_repository.get_by_id(experiment_id)
        if exp and exp.status == "draft":
            return self.experiments_repository.update(experiment_id, status="running")
        return None

    def complete_experiment(self, experiment_id: Any, result_summary: str, result_data: Optional[Dict[str, Any]] = None) -> Optional[Experiment]:
        exp = self.experiments_repository.get_by_id(experiment_id)
        if exp and exp.status == "running":
            exp = self.experiments_repository.update(
                experiment_id, status="completed", result_summary=result_summary, result_data=result_data or {}
            )
            self.event_bus.publish(
                ExperimentFinished(experiment_id=exp.id, hypothesis_id=exp.hypothesis_id, outcome="completed")
            )
            return exp
        return None

    def abort_experiment(self, experiment_id: Any, reason: Optional[str] = None) -> Optional[Experiment]:
        exp = self.experiments_repository.get_by_id(experiment_id)
        if exp and exp.status in ["draft", "running"]:
            exp = self.experiments_repository.update(experiment_id, status="aborted", result_summary=reason)
            self.event_bus.publish(
                ExperimentFinished(experiment_id=exp.id, hypothesis_id=exp.hypothesis_id, outcome="aborted")
            )
            return exp
        return None

    def get_experiment_summary(self) -> Dict[str, int]:
        summary: Dict[str, int] = {}
        for e in self.experiments_repository.list_all():
            summary[e.status] = summary.get(e.status, 0) + 1
        return summary

    def list_running_experiments(self) -> List[Experiment]:
        return self.experiments_repository.list_by_status("running")


experiment_service = ExperimentService()
