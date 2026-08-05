"""
Verifies the migration system itself: fresh-database bootstrap, idempotency,
schema_version bookkeeping, and that every table the project depends on
(Phase 1 operational + Phase 2 structural foundation) actually exists after
running the full migration chain once.
"""
from __future__ import annotations

from sqlalchemy import text

EXPECTED_TABLES = {
    # Phase 1 — baseline (version 1)
    "topics", "posts", "designs", "media",
    "publishing_schedule", "publishing_history", "metrics", "schema_version",
    # Phase 2 structural foundation (migration 0002)
    "features", "scores", "knowledge_versions", "knowledge_rules",
    "rule_lifecycle_events", "hypotheses", "experiments", "memory_entries",
    "weekly_plans", "strategy_history", "decision_logs", "confidence_scores",
    "quality_results", "engine_health", "notifications", "event_logs",
    "system_settings", "prompt_versions", "model_versions", "failures",
    "explainability_notes", "audit_log",
}


def test_all_expected_tables_exist(engine, _migrated_database):
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        )
        actual_tables = {row[0] for row in rows}

    missing = EXPECTED_TABLES - actual_tables
    assert not missing, f"Missing tables after migration: {sorted(missing)}"


def test_schema_version_recorded_both_migrations(engine, _migrated_database):
    with engine.connect() as conn:
        versions = {row[0] for row in conn.execute(text("SELECT version FROM schema_version"))}
    assert 1 in versions, "Baseline (version 1) was not recorded in schema_version."
    assert 2 in versions, "Migration 0002 was not recorded in schema_version."
    assert 3 in versions, "Migration 0003 was not recorded in schema_version."


def test_migrations_are_idempotent(engine, _migrated_database):
    """Running the migration manager again on an already-migrated database
    must be a safe no-op, not an error and not a duplicate application."""
    from database.migration_manager import MigrationManager

    manager = MigrationManager(engine)
    applied_again = manager.run_pending()
    assert applied_again == [], "Re-running migrations on an up-to-date database should apply nothing."


def test_fresh_database_bootstrap_from_zero(engine):
    """Independent of the session-scoped fixture: drop everything and prove
    a completely blank database reaches the same final version on its own."""
    from database.migration_manager import MigrationManager

    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))

    manager = MigrationManager(engine)
    applied = manager.run_pending()
    assert "0001_initial_schema" in applied
    assert any(name.startswith("0002_") for name in applied)
    assert any(name.startswith("0003_") for name in applied)

    with engine.connect() as conn:
        current_version = conn.execute(text("SELECT MAX(version) FROM schema_version")).scalar_one()
    assert current_version == 3
