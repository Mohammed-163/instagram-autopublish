import os
import pytest
from database import seed
from database.repositories import settings_repository, engine_health_repository

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="DATABASE_URL is not set — skipping live database tests."
)

def test_seed_is_idempotent(_migrated_database):
    # Run twice
    seed.run()
    seed.run()
    
    # Check that there are 10 engines
    engines = engine_health_repository.list_all()
    assert len(engines) == 10

def test_seed_creates_settings(_migrated_database):
    seed.run()
    val = settings_repository.get("min_confidence_threshold")
    assert val is not None

def test_seed_creates_engine_health(_migrated_database):
    seed.run()
    engines = engine_health_repository.list_all()
    names = [e.engine_name for e in engines]
    assert "observation_engine" in names
    assert "notification_engine" in names
