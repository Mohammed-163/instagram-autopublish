"""
Verifies relationships and constraints: FKs cascade correctly, CHECK
constraints reject invalid values, and UNIQUE constraints are enforced —
on both Phase 1 tables and the new Phase 2 foundation tables.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DataError, IntegrityError


def _insert_topic(conn, name="Psychology", slug="psychology"):
    return conn.execute(
        text("INSERT INTO topics (name, slug) VALUES (:n, :s) RETURNING id"),
        {"n": name, "s": slug},
    ).scalar_one()


def _insert_post(conn, topic_id=None, status="draft"):
    return conn.execute(
        text("INSERT INTO posts (topic_id, status) VALUES (:t, :s) RETURNING id"),
        {"t": topic_id, "s": status},
    ).scalar_one()


def test_post_status_check_constraint_rejects_invalid_value(engine, _migrated_database):
    with engine.connect() as conn, pytest.raises(IntegrityError):
        with conn.begin():
            conn.execute(text("INSERT INTO posts (status) VALUES ('not_a_real_status')"))


def test_knowledge_rule_lifecycle_state_check_constraint(engine, _migrated_database):
    with engine.connect() as conn, pytest.raises(IntegrityError):
        with conn.begin():
            conn.execute(
                text(
                    "INSERT INTO knowledge_rules (name, conditions, action, lifecycle_state) "
                    "VALUES ('x', '{}'::jsonb, '{}'::jsonb, 'not_a_real_state')"
                )
            )


def test_posts_deleting_cascades_to_designs_and_metrics(engine, _migrated_database):
    with engine.begin() as conn:
        post_id = _insert_post(conn)
        conn.execute(text("INSERT INTO designs (post_id) VALUES (:p)"), {"p": post_id})
        conn.execute(
            text(
                "INSERT INTO metrics (post_id, snapshot_period, captured_at) "
                "VALUES (:p, '24h', now())"
            ),
            {"p": post_id},
        )

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM posts WHERE id = :p"), {"p": post_id})
        design_count = conn.execute(
            text("SELECT COUNT(*) FROM designs WHERE post_id = :p"), {"p": post_id}
        ).scalar_one()
        metric_count = conn.execute(
            text("SELECT COUNT(*) FROM metrics WHERE post_id = :p"), {"p": post_id}
        ).scalar_one()

    assert design_count == 0
    assert metric_count == 0


def test_deleting_topic_sets_post_topic_id_null(engine, _migrated_database):
    with engine.begin() as conn:
        topic_id = _insert_topic(conn, name="Nutrition Facts Test", slug="nutrition-facts-test")
        post_id = _insert_post(conn, topic_id=topic_id)

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM topics WHERE id = :t"), {"t": topic_id})

    with engine.connect() as conn:
        remaining_topic_id = conn.execute(
            text("SELECT topic_id FROM posts WHERE id = :p"), {"p": post_id}
        ).scalar_one()
    assert remaining_topic_id is None


def test_metrics_unique_constraint_on_post_and_period(engine, _migrated_database):
    with engine.begin() as conn:
        post_id = _insert_post(conn)
        conn.execute(
            text("INSERT INTO metrics (post_id, snapshot_period, captured_at) VALUES (:p, '24h', now())"),
            {"p": post_id},
        )

    with engine.connect() as conn, pytest.raises(IntegrityError):
        with conn.begin():
            conn.execute(
                text("INSERT INTO metrics (post_id, snapshot_period, captured_at) VALUES (:p, '24h', now())"),
                {"p": post_id},
            )


def test_features_unique_constraint_on_post_and_key(engine, _migrated_database):
    with engine.begin() as conn:
        post_id = _insert_post(conn)
        conn.execute(
            text("INSERT INTO features (post_id, feature_key, feature_value) VALUES (:p, 'word_count', 12)"),
            {"p": post_id},
        )

    with engine.connect() as conn, pytest.raises(IntegrityError):
        with conn.begin():
            conn.execute(
                text("INSERT INTO features (post_id, feature_key, feature_value) VALUES (:p, 'word_count', 99)"),
                {"p": post_id},
            )


def test_deleting_knowledge_rule_cascades_to_lifecycle_events(engine, _migrated_database):
    with engine.begin() as conn:
        rule_id = conn.execute(
            text(
                "INSERT INTO knowledge_rules (name, conditions, action) "
                "VALUES ('test rule', '{}'::jsonb, '{}'::jsonb) RETURNING id"
            )
        ).scalar_one()
        conn.execute(
            text("INSERT INTO rule_lifecycle_events (rule_id, to_state) VALUES (:r, 'active')"),
            {"r": rule_id},
        )

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM knowledge_rules WHERE id = :r"), {"r": rule_id})

    with engine.connect() as conn:
        remaining = conn.execute(
            text("SELECT COUNT(*) FROM rule_lifecycle_events WHERE rule_id = :r"), {"r": rule_id}
        ).scalar_one()
    assert remaining == 0
