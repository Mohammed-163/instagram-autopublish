"""
Bootstrap entrypoint.

Provides only `run(event)`. No sample generators, no demo data, no
HTTP server, no scheduler.
"""
from __future__ import annotations

from typing import Optional

from phase9_coverage.application.container import Container, build_container
from phase9_coverage.domain.inbound_events import KnowledgeValidated
from phase9_coverage.domain.models import CoverageProfile
from phase9_coverage.events.events import KnowledgeCoverageCalculated

_container: Optional[Container] = None


def _get_container() -> Container:
    global _container
    if _container is None:
        _container = build_container(ensure_schema=True)
    return _container


def run(
    event: KnowledgeValidated,
    coverage_profile: Optional[CoverageProfile] = None,
) -> KnowledgeCoverageCalculated:
    """
    Single entrypoint: takes a KnowledgeValidated event, runs it through
    the engine, and returns the resulting KnowledgeCoverageCalculated
    event. Lazily builds and reuses a module-level container.
    """
    container = _get_container()
    return container.engine.handle(event, coverage_profile=coverage_profile)
