"""conftest for Phase9 tests."""
from __future__ import annotations
import os, sys, pytest

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, _project_root)

# Phase5/6 first to cache its namespaces, then phase9
import phase5_6
from core.container import container as _c  # trigger full bootstrap
import phase9_coverage

from phase9_coverage.application.container import Container, build_container
from phase9_coverage.config.settings import Settings
from phase9_coverage.database.session import create_db_engine, create_session_factory, init_schema
from phase9_coverage.events.publisher import InMemoryEventPublisher


@pytest.fixture()
def test_settings() -> Settings:
    return Settings(
        schema_version="1.0.0",
        engine_version="1.0.0",
        fingerprint_version="1.0.0",
        coverage_version="1.0.0",
        database_url="sqlite+pysqlite:///:memory:",
    )


@pytest.fixture()
def container(test_settings: Settings) -> Container:
    db_engine = create_db_engine(test_settings)
    init_schema(db_engine)
    session_factory = create_session_factory(db_engine)
    session = session_factory()
    publisher = InMemoryEventPublisher()
    return build_container(settings=test_settings, session=session, publisher=publisher)
