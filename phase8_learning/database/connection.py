"""
Database connection factory and Unit of Work.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from phase8_learning.config.settings import Settings
from phase8_learning.database.models import Base


class DatabaseConnectionFactory:
    """
    Creates and owns the SQLAlchemy Engine and session factory for the
    Learning Layer, based on Settings.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        connect_args = (
            {"check_same_thread": False}
            if settings.database_url.startswith("sqlite")
            else {}
        )
        self._engine: Engine = create_engine(
            settings.database_url, connect_args=connect_args, future=True
        )
        self._session_factory = sessionmaker(
            bind=self._engine, expire_on_commit=False, future=True
        )

    @property
    def engine(self) -> Engine:
        return self._engine

    def create_all(self) -> None:
        """Create all tables. Intended for local/dev use; production should
        rely on the migrations/ directory."""
        Base.metadata.create_all(self._engine)

    def new_session(self) -> Session:
        return self._session_factory()


class UnitOfWork:
    """
    A minimal Unit of Work wrapping a single SQLAlchemy Session, used to
    scope repository operations to a single atomic transaction.
    """

    def __init__(self, connection_factory: DatabaseConnectionFactory) -> None:
        self._connection_factory = connection_factory
        self.session: Optional[Session] = None

    def __enter__(self) -> "UnitOfWork":
        self.session = self._connection_factory.new_session()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        assert self.session is not None
        try:
            if exc_type is not None:
                self.session.rollback()
            else:
                self.session.commit()
        finally:
            self.session.close()
            self.session = None

    def commit(self) -> None:
        assert self.session is not None
        self.session.commit()

    def rollback(self) -> None:
        assert self.session is not None
        self.session.rollback()
