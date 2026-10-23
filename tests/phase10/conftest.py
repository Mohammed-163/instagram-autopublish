"""Shared pytest fixtures for Phase10 integration tests."""
from __future__ import annotations
import os, sys, pytest

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, _project_root)

import phase5_6
from core.container import container as _c  # bootstrap Phase5/6 first
import phase10_intelligence

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from phase10_intelligence.config.settings import Settings
from phase10_intelligence.di.container import Container
from phase10_intelligence.events.publisher import InMemoryEventPublisher
from phase10_intelligence.orm.base import Base


@pytest.fixture()
def settings() -> Settings:
    return Settings()


@pytest.fixture()
def session(settings):
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    sess = factory()
    yield sess
    sess.close()


@pytest.fixture()
def publisher():
    return InMemoryEventPublisher()


@pytest.fixture()
def container(session, settings, publisher) -> Container:
    return Container(session, settings, publisher)
