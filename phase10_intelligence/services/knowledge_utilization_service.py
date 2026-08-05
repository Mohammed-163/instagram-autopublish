"""
KnowledgeUtilizationService

All business logic for this layer lives here. This service reads its
thresholds/weights exclusively from Settings; no business constants
are hard-coded in this module.
"""
from __future__ import annotations

from typing import List

from ..config.settings import Settings
from ..domain.models import MemoryRecord
from ..repositories.memory_repository import MemoryRepository


class KnowledgeUtilizationService:
    """Surfaces relevant prior knowledge for a given subject type."""

    def __init__(self, repository: MemoryRepository, settings: Settings) -> None:
        self._repository = repository
        self._settings = settings

    def relevant_knowledge(self, subject_type: str) -> List[MemoryRecord]:
        return self._repository.list_relevant(
            subject_type, self._settings.knowledge_utilization_min_relevance
        )
