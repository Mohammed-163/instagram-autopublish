import os
import pytest
from database import queries

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="DATABASE_URL is not set — skipping live database tests."
)

def test_dashboard_data_returns_structure(_migrated_database):
    data = queries.get_system_dashboard_data()
    assert "active_posts" in data
    assert "failed_posts" in data
    assert "active_rules" in data

def test_best_posts_query(_migrated_database):
    # Just asserting it doesn't crash on an empty db
    posts = queries.get_best_posts_last_n_days(days=30, limit=20)
    assert isinstance(posts, list)

def test_quality_gate_pass_rates(_migrated_database):
    rates = queries.get_quality_gate_pass_rates(days=30)
    assert isinstance(rates, dict)
