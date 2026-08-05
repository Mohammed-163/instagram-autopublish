"""
Dependency injection container.

Registers, in order: repository, service, engine, publisher. Wiring
only — no business logic, no fingerprinting, no persistence logic.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from phase9_coverage.config.settings import Settings, get_settings
from phase9_coverage.database.session import create_db_engine, create_session_factory, init_schema
from phase9_coverage.engine.knowledge_coverage_engine import KnowledgeCoverageEngine
from phase9_coverage.events.publisher import EventPublisher, InMemoryEventPublisher
from phase9_coverage.repository.knowledge_coverage_repository import KnowledgeCoverageRepository
from phase9_coverage.service.knowledge_coverage_service import KnowledgeCoverageService


@dataclass
class Container:
    """Holds fully-wired components for a single request/session scope."""

    settings: Settings
    session: Session
    repository: KnowledgeCoverageRepository
    publisher: EventPublisher
    service: KnowledgeCoverageService
    engine: KnowledgeCoverageEngine


def build_container(
    settings: Settings | None = None,
    session: Session | None = None,
    publisher: EventPublisher | None = None,
    ensure_schema: bool = False,
) -> Container:
    """
    Builds a fully-wired Container.

    - settings: loaded from environment if not provided.
    - session: a new SQLAlchemy session bound to a fresh engine, if not provided.
    - publisher: an InMemoryEventPublisher, if not provided.
    - ensure_schema: if True, creates tables via metadata (useful for
      tests/local runs; production should rely on Alembic migrations).
    """
    resolved_settings = settings or get_settings()

    if session is None:
        db_engine = create_db_engine(resolved_settings)
        if ensure_schema:
            init_schema(db_engine)
        session_factory = create_session_factory(db_engine)
        session = session_factory()

    resolved_publisher = publisher or InMemoryEventPublisher()

    repository = KnowledgeCoverageRepository(session)
    service = KnowledgeCoverageService(
        repository=repository, publisher=resolved_publisher, settings=resolved_settings
    )
    engine = KnowledgeCoverageEngine(service=service)

    return Container(
        settings=resolved_settings,
        session=session,
        repository=repository,
        publisher=resolved_publisher,
        service=service,
        engine=engine,
    )
