from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from engines.opportunity_detectors.opportunity_candidate import OpportunityCandidate


class BaseDetector(ABC):
    """Interface every Opportunity Detector plugin must implement.

    Rules (enforced by design):
    - Pure function of the data passed in (knowledge_context dict)
    - No DB access
    - No LLM calls
    - No hardcoded thresholds (all read from `settings` dict passed in)
    - Must be deterministic: same input -> same output, always
    - Returns List[OpportunityCandidate], NEVER plain dicts
    """

    @property
    @abstractmethod
    def detector_name(self) -> str:
        """Unique name identifying this detector."""
        raise NotImplementedError

    @property
    @abstractmethod
    def version(self) -> str:
        """Semantic version of this detector's logic.
        Bump whenever logic changes so historical records stay interpretable.
        """
        raise NotImplementedError

    @abstractmethod
    def detect(
        self,
        knowledge_context: Dict[str, Any],
        settings: Dict[str, Any],
    ) -> List[OpportunityCandidate]:
        """Detect opportunities from a knowledge context snapshot.

        Args:
            knowledge_context: dict with all data needed — rules, stats,
                               coverage, features. NO direct DB calls here.
            settings: dict of thresholds/weights from SettingsService.
                      ALL configuration must come from here, not hardcoded.

        Returns:
            List of OpportunityCandidate objects. Empty list if none found.
            Every returned candidate MUST have a valid Evidence object.
        """
        raise NotImplementedError
