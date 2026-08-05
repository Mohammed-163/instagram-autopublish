"""
Application bootstrap: builds the SQLAlchemy engine/session factory,
runs schema creation, and constructs the DI Container.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..config.settings import Settings, get_settings
from ..di.container import Container
from ..events.publisher import EventPublisher, InMemoryEventPublisher
from ..orm.base import Base


@dataclass
class Application:
    """Holds the wired engine/session factory and provides a Container per unit of work."""

    settings: Settings
    engine: object
    session_factory: sessionmaker
    publisher: EventPublisher

    def new_session(self) -> Session:
        return self.session_factory()

    def new_container(self, session: Optional[Session] = None) -> Container:
        owned_session = session or self.new_session()
        return Container(owned_session, self.settings, self.publisher)


def create_application(settings: Optional[Settings] = None,
                        publisher: Optional[EventPublisher] = None,
                        create_schema: bool = True) -> Application:
    """Construct the standalone application: engine, schema, session factory."""
    resolved_settings = settings or get_settings()
    engine = create_engine(resolved_settings.database_url, echo=resolved_settings.sql_echo, future=True)

    if create_schema:
        Base.metadata.create_all(engine)

    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    resolved_publisher = publisher or InMemoryEventPublisher()

    return Application(
        settings=resolved_settings, engine=engine,
        session_factory=session_factory, publisher=resolved_publisher,
    )
