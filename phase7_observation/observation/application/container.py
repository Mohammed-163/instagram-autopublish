"""
Dependency Injection Container.

Assembles the full object graph:
  DatabaseConnectionFactory → UnitOfWork → Repository → Service → Engine

This is the single place where concrete types are chosen.
Nothing outside this module needs to know which implementations are used.
"""
from __future__ import annotations

from observation.config.settings import Settings
from observation.domain.engine import ObservationEngine
from observation.domain.service import ObservationService
from observation.infrastructure.db.connection import DatabaseConnectionFactory
from observation.infrastructure.db.unit_of_work import UnitOfWork
from observation.infrastructure.events.publishers import (
    CompositeEventPublisher,
    InProcessEventPublisher,
    LoggingEventPublisher,
)
from observation.infrastructure.repository.observation_queries import (
    ObservationQueryService,
)
from observation.infrastructure.repository.observation_repository import (
    SQLAlchemyObservationRepository,
)


class ObservationContainer:
    """
    Holds singleton-scoped infrastructure objects and provides factory methods
    for request-scoped objects (UoW, Session).

    Lifecycle:
        container = ObservationContainer(settings)
        container.bootstrap()      # one-time setup
        ...
        container.shutdown()       # on process exit
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

        # --- Singletons built in bootstrap() ---
        self._db_factory: DatabaseConnectionFactory | None = None
        self._in_process_publisher: InProcessEventPublisher | None = None
        self._logging_publisher: LoggingEventPublisher | None = None
        self._composite_publisher: CompositeEventPublisher | None = None
        self._engine: ObservationEngine | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def bootstrap(self) -> None:
        """Wire the full object graph.  Call once at process startup."""
        # 1. Database connection factory (singleton)
        self._db_factory = DatabaseConnectionFactory(self._settings.database)

        # 2. Event publishers (singletons)
        self._in_process_publisher = InProcessEventPublisher()
        self._logging_publisher = LoggingEventPublisher()
        self._composite_publisher = CompositeEventPublisher(
            self._in_process_publisher,
            self._logging_publisher,
        )

        # 3. Domain service (singleton — stateless after construction)
        service = ObservationService(
            repository=self._build_repository(),
            publisher=self._composite_publisher,
            observation_version=self._settings.versions.observation_version,
            fingerprint_version=self._settings.versions.fingerprint_version,
        )

        # 4. ObservationEngine (singleton façade)
        self._engine = ObservationEngine(service=service)

    def shutdown(self) -> None:
        """Release resources.  Call on process exit."""
        if self._db_factory is not None:
            self._db_factory.dispose()

    # ------------------------------------------------------------------
    # Accessors (singletons)
    # ------------------------------------------------------------------

    @property
    def engine(self) -> ObservationEngine:
        self._require_bootstrapped()
        return self._engine  # type: ignore[return-value]

    @property
    def in_process_publisher(self) -> InProcessEventPublisher:
        self._require_bootstrapped()
        return self._in_process_publisher  # type: ignore[return-value]

    @property
    def db_factory(self) -> DatabaseConnectionFactory:
        self._require_bootstrapped()
        return self._db_factory  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Factories (request-scoped)
    # ------------------------------------------------------------------

    def unit_of_work(self) -> UnitOfWork:
        """Return a fresh UnitOfWork for a single operation."""
        self._require_bootstrapped()
        return UnitOfWork(self._db_factory)  # type: ignore[arg-type]

    def query_service(self) -> ObservationQueryService:
        """Return a query service bound to a fresh read-only session."""
        self._require_bootstrapped()
        session = self._db_factory.new_session()  # type: ignore[union-attr]
        return ObservationQueryService(session)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_repository(self) -> SQLAlchemyObservationRepository:
        """
        Build a repository against a transient session.
        The service will open a new UoW per operation via the container.
        Note: for the domain service to use UoW properly, the repository
        must be constructed per-request in the application layer. This
        singleton wiring is for convenience; see ApplicationBootstrap for
        the per-request pattern.
        """
        session = self._db_factory.new_session()  # type: ignore[union-attr]
        return SQLAlchemyObservationRepository(session)

    def _require_bootstrapped(self) -> None:
        if self._engine is None:
            raise RuntimeError(
                "ObservationContainer.bootstrap() must be called before use."
            )
