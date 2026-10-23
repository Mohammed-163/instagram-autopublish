"""
DatabaseConnectionFactory.

Sole responsibility: create a SQLAlchemy Engine and sessionmaker from
configuration.  No business logic, no ORM model knowledge.
"""
from __future__ import annotations

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session

from observation.config.settings import DatabaseSettings


class DatabaseConnectionFactory:
    """
    Creates and owns the SQLAlchemy Engine and SessionFactory.
    Instantiated once per process; the session factory produces
    per-unit-of-work sessions.
    """

    def __init__(self, settings: DatabaseSettings) -> None:
        self._settings = settings
        self._engine: Engine | None = None
        self._session_factory: sessionmaker | None = None

    # ------------------------------------------------------------------
    # Engine
    # ------------------------------------------------------------------

    def engine(self) -> Engine:
        if self._engine is None:
            self._engine = create_engine(
                self._settings.dsn,
                pool_size=self._settings.pool_size,
                max_overflow=self._settings.max_overflow,
                echo=self._settings.echo_sql,
                future=True,
            )
        return self._engine

    # ------------------------------------------------------------------
    # Session factory
    # ------------------------------------------------------------------

    def session_factory(self) -> sessionmaker:
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                bind=self.engine(),
                autocommit=False,
                autoflush=False,
                expire_on_commit=False,
            )
        return self._session_factory

    def new_session(self) -> Session:
        """Convenience: open a fresh SQLAlchemy Session."""
        return self.session_factory()()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def dispose(self) -> None:
        """Release all pooled connections.  Call on process shutdown."""
        if self._engine is not None:
            self._engine.dispose()
