"""
Application Bootstrap.

Provides the canonical per-request wiring pattern:
  DatabaseConnectionFactory → UnitOfWork → Repository → Service → Engine

Use this when you need full transactional control per event/command.
The container is for long-lived singletons; bootstrap is for request scope.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from observation.config.settings import Settings
from observation.domain.engine import ObservationEngine
from observation.domain.events import DomainEvent
from observation.infrastructure.db.connection import DatabaseConnectionFactory
from observation.infrastructure.db.unit_of_work import UnitOfWork
from observation.infrastructure.events.publishers import (
    CompositeEventPublisher,
    InProcessEventPublisher,
    LoggingEventPublisher,
)
from observation.infrastructure.repository.observation_repository import (
    SQLAlchemyObservationRepository,
)
from observation.domain.service import ObservationService


class ApplicationBootstrap:
    """
    Builds and tears down the full dependency graph per event handling cycle.

    Each call to `handle_event` opens a fresh UnitOfWork, wires repository
    and service against it, dispatches the event, commits (or rolls back),
    and closes the session — ensuring clean transaction boundaries.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._db_factory = DatabaseConnectionFactory(settings.database)
        self._in_process_publisher = InProcessEventPublisher()
        self._logging_publisher = LoggingEventPublisher()
        self._publisher = CompositeEventPublisher(
            self._in_process_publisher,
            self._logging_publisher,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle_event(self, event: DomainEvent) -> None:
        """
        Route a domain event through a fresh transactional scope.
        Commits on success; rolls back on any exception.
        """
        with UnitOfWork(self._db_factory) as uow:
            engine = self._build_engine(uow)
            engine.handle(event)
            uow.commit()

    @property
    def in_process_publisher(self) -> InProcessEventPublisher:
        """Expose so callers can register handlers before events arrive."""
        return self._in_process_publisher

    def shutdown(self) -> None:
        self._db_factory.dispose()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_engine(self, uow: UnitOfWork) -> ObservationEngine:
        """Construct the full object graph scoped to one UnitOfWork."""
        repository = SQLAlchemyObservationRepository(uow.session)
        service = ObservationService(
            repository=repository,
            publisher=self._publisher,
            observation_version=self._settings.versions.observation_version,
            fingerprint_version=self._settings.versions.fingerprint_version,
        )
        return ObservationEngine(service=service)
