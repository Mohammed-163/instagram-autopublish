"""
Database engine/session factory. No business logic. No repository
logic. Just SQLAlchemy plumbing driven entirely by Settings.
"""
from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from phase9_coverage.config.settings import Settings
from phase9_coverage.database.models import Base


def create_db_engine(settings: Settings) -> Engine:
    connect_args = {}
    extra_kwargs = {}
    if settings.database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        if ":memory:" in settings.database_url:
            # In-memory SQLite only persists for the life of a single
            # connection; pin the engine to one shared connection so
            # tables created via init_schema remain visible across
            # subsequent sessions/queries in the same process.
            extra_kwargs = {"poolclass": StaticPool}
    return create_engine(
        settings.database_url, connect_args=connect_args, future=True, **extra_kwargs
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_schema(engine: Engine) -> None:
    """Creates all tables. Intended for tests/local dev; production uses Alembic."""
    Base.metadata.create_all(engine)
