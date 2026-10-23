"""
Shared pytest fixtures for the database test suite.
"""
from __future__ import annotations

import os
import pytest
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL")


@pytest.fixture(scope="session")
def engine():
    if not DATABASE_URL:
        pytest.skip("DATABASE_URL is not set.")
    eng = create_engine(DATABASE_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture(scope="session", autouse=True)
def _migrated_database(request):
    """Applies every migration once for the whole test session if DATABASE_URL is provided."""
    if not DATABASE_URL:
        return None

    eng = create_engine(DATABASE_URL, future=True)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))

    from database.migration_manager import MigrationManager

    manager = MigrationManager(eng)
    applied = manager.run_pending()
    eng.dispose()
    return applied


@pytest.fixture()
def session(engine):
    from sqlalchemy.orm import Session

    with Session(engine, expire_on_commit=False) as s:
        yield s
        s.rollback()
