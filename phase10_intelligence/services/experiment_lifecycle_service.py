"""
ExperimentLifecycleService

All business logic for this layer lives here. This service reads its
thresholds/weights exclusively from Settings; no business constants
are hard-coded in this module.
"""
from __future__ import annotations

from typing import Optional

from ..config.settings import Settings
from ..domain.enums import ExperimentStatus
from ..domain.models import Experiment, Hypothesis
from ..events import EventPublisher, ExperimentCompleted
from ..fingerprint import compute_fingerprint
from ..repositories.experiment_repository import ExperimentRepository


class ExperimentLifecycleService:
    """Manages planning, execution bookkeeping, and analysis of experiments."""

    def __init__(self, repository: ExperimentRepository, settings: Settings,
                 publisher: EventPublisher) -> None:
        self._repository = repository
        self._settings = settings
        self._publisher = publisher

    def plan(self, key: str, hypothesis: Hypothesis) -> Optional[Experiment]:
        running = len(self._repository.list_by_status(ExperimentStatus.RUNNING))
        if running >= self._settings.experiment_max_concurrent:
            return None

        payload = {"key": key, "hypothesis_key": hypothesis.key}
        fp = compute_fingerprint(payload)

        experiment = Experiment(
            id=None, key=key, hypothesis_id=hypothesis.id, status=ExperimentStatus.PLANNED,
            sample_size=0, effect_size=None, p_value=None, fingerprint=fp,
        )
        return self._repository.add(experiment)

    def record_result(self, experiment: Experiment, sample_size: int,
                       effect_size: float, p_value: float) -> Experiment:
        status = (
            ExperimentStatus.ANALYZED
            if sample_size >= self._settings.experiment_min_sample_size
            and p_value <= self._settings.experiment_significance_threshold
            else ExperimentStatus.COMPLETED
        )
        self._repository.update(experiment.key, status, sample_size, effect_size, p_value)
        stored = self._repository.get_by_key(experiment.key)

        self._publisher.publish(ExperimentCompleted(
            subject_key=stored.key, fingerprint=stored.fingerprint,
            payload={"status": stored.status.value, "p_value": p_value},
        ))
        return stored

    def is_significant(self, experiment: Experiment) -> bool:
        if experiment.p_value is None or experiment.sample_size < self._settings.experiment_min_sample_size:
            return False
        return experiment.p_value <= self._settings.experiment_significance_threshold
