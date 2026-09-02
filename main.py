"""
Minimal entrypoint for the Learning Layer.

Demonstrates the flow:

    ObservationRecorded
        v
    LearningEngine
        v
    LearningService
        v
    Repository

No HTTP. No queues. No sample or fake data lives in this module — it is
meant to be imported and called by a real caller that already owns a
stream of ObservationRecorded events produced by the upstream Observation
layer.
"""

from __future__ import annotations

import logging
from typing import Iterable, List, Optional

from phase8_learning.config.settings import Settings
from phase8_learning.domain.knowledge import Knowledge
from phase8_learning.events.events import ObservationRecorded
from phase8_learning.infrastructure.container import Container

logger = logging.getLogger(__name__)


def run(
    observations: Iterable[ObservationRecorded],
    settings: Optional[Settings] = None,
) -> List[Knowledge]:
    """
    Run one batch of ObservationRecorded events through the full
    Engine -> Service -> Repository pipeline and return the Knowledge
    objects that were created or updated.
    """
    container = Container(settings=settings)
    container.initialize_schema()

    stack = container.build_stack()
    try:
        incoming = list(observations)
        pairs = {(o.subject_id, o.metric_name) for o in incoming}
        from phase8_learning.repository.learning_observation_repository import latest_for_pairs
        historical = latest_for_pairs(stack.unit_of_work.session, pairs, limit=100)
        seen = {str(o.observation_id) for o in incoming}
        restored = [
            ObservationRecorded(
                observation_id=str(row.observation_id or row.id),
                subject_id=row.subject_id,
                metric_name=row.metric_name,
                metric_value=float(row.metric_value),
                context=row.context or {},
            )
            for row in historical
            if str(row.observation_id or row.id) not in seen
        ]
        all_observations = restored + incoming
        logger.warning(
            "[DEBUG] Calling LearningEngine.process with %d total observations "
            "(historical=%d, current=%d)",
            len(all_observations), len(historical), len(incoming),
        )
        candidates = stack.engine.process(all_observations)
        results = stack.service.process_candidates(list(candidates))
        stack.unit_of_work.commit()
        return results
    except Exception:
        stack.unit_of_work.rollback()
        raise
    finally:
        stack.unit_of_work.__exit__(None, None, None)
