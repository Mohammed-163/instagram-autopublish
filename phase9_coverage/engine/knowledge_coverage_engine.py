"""
KnowledgeCoverageEngine.

Consumes KnowledgeValidated, produces KnowledgeCoverageCalculated.

Hard constraints (enforced by construction, not by convention):
  - Never accesses a repository directly.
  - Never generates fingerprints.
  - Never validates knowledge.
  - Never publishes events directly.

It only ever calls KnowledgeCoverageService.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from phase9_coverage.domain.inbound_events import KnowledgeValidated
from phase9_coverage.domain.models import CoverageProfile
from phase9_coverage.events.events import KnowledgeCoverageCalculated
from phase9_coverage.service.knowledge_coverage_service import KnowledgeCoverageService


class KnowledgeCoverageEngine:
    """Thin orchestration layer between inbound events and the service."""

    def __init__(self, service: KnowledgeCoverageService) -> None:
        self._service = service

    def handle(
        self,
        event: KnowledgeValidated,
        coverage_profile: Optional[CoverageProfile] = None,
    ) -> KnowledgeCoverageCalculated:
        """
        Processes a single KnowledgeValidated event end-to-end by
        delegating entirely to the service, then returns the
        KnowledgeCoverageCalculated event that resulted from it.
        """
        result = self._service.calculate_coverage(event, coverage_profile=coverage_profile)
        return KnowledgeCoverageCalculated(
            coverage=result.coverage,
            occurred_at=result.coverage.created_at,
        )
