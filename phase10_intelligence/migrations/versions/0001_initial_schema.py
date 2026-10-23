"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "opportunities",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(128), nullable=False, unique=True),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("description", sa.String(1024), nullable=False),
        sa.Column("raw_signal", sa.JSON, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("impact_estimate", sa.Float, nullable=False),
        sa.Column("novelty_score", sa.Float, nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_table(
        "opportunity_rankings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("opportunity_id", sa.Integer, sa.ForeignKey("opportunities.id"), nullable=False),
        sa.Column("rank_score", sa.Float, nullable=False),
        sa.Column("components", sa.JSON, nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_table(
        "opportunity_validations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("opportunity_id", sa.Integer, sa.ForeignKey("opportunities.id"), nullable=False),
        sa.Column("is_valid", sa.Boolean, nullable=False),
        sa.Column("evidence_count", sa.Integer, nullable=False),
        sa.Column("reasons", sa.JSON, nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_table(
        "hypotheses",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(128), nullable=False, unique=True),
        sa.Column("statement", sa.String(1024), nullable=False),
        sa.Column("origin_opportunity_id", sa.Integer, sa.ForeignKey("opportunities.id"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("cycles_active", sa.Integer, nullable=False, server_default="0"),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_table(
        "experiments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(128), nullable=False, unique=True),
        sa.Column("hypothesis_id", sa.Integer, sa.ForeignKey("hypotheses.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("sample_size", sa.Integer, nullable=False, server_default="0"),
        sa.Column("effect_size", sa.Float, nullable=True),
        sa.Column("p_value", sa.Float, nullable=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_table(
        "strategies",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(128), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("parameters", sa.JSON, nullable=False),
        sa.Column("generation", sa.Integer, nullable=False, server_default="0"),
        sa.Column("parent_key", sa.String(128), nullable=True),
        sa.Column("fitness_score", sa.Float, nullable=False, server_default="0"),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_table(
        "strategy_evaluations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("strategy_id", sa.Integer, sa.ForeignKey("strategies.id"), nullable=False),
        sa.Column("fitness_score", sa.Float, nullable=False),
        sa.Column("metrics", sa.JSON, nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_table(
        "rules",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(128), nullable=False, unique=True),
        sa.Column("condition_expression", sa.String(1024), nullable=False),
        sa.Column("action_expression", sa.String(1024), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("generation", sa.Integer, nullable=False, server_default="0"),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_table(
        "governance_reviews",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("subject_type", sa.String(64), nullable=False),
        sa.Column("subject_key", sa.String(128), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("risk_score", sa.Float, nullable=False),
        sa.Column("approvals", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rationale", sa.String(1024), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.UniqueConstraint("subject_type", "subject_key", "fingerprint", name="uq_governance_subject_fp"),
    )
    op.create_table(
        "confidence_calibrations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("subject_type", sa.String(64), nullable=False),
        sa.Column("subject_key", sa.String(128), nullable=False),
        sa.Column("raw_confidence", sa.Float, nullable=False),
        sa.Column("calibrated_confidence", sa.Float, nullable=False),
        sa.Column("sample_size", sa.Integer, nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_table(
        "planning_cycles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("cycle_index", sa.Integer, nullable=False, unique=True),
        sa.Column("horizon", sa.Integer, nullable=False),
        sa.Column("selected_strategy_keys", sa.JSON, nullable=False),
        sa.Column("risk_budget_used", sa.Float, nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_table(
        "memory_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("subject_type", sa.String(64), nullable=False),
        sa.Column("subject_key", sa.String(128), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("relevance_score", sa.Float, nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.UniqueConstraint("subject_type", "subject_key", "fingerprint", name="uq_memory_subject_fp"),
    )
    op.create_table(
        "feedback_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("subject_type", sa.String(64), nullable=False),
        sa.Column("subject_key", sa.String(128), nullable=False),
        sa.Column("outcome_score", sa.Float, nullable=False),
        sa.Column("applied_learning_rate", sa.Float, nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_table(
        "replay_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("subject_type", sa.String(64), nullable=False),
        sa.Column("subject_key", sa.String(128), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("output_fingerprint", sa.String(64), nullable=False),
        sa.Column("engine_name", sa.String(128), nullable=False),
        sa.Column("engine_version", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_table(
        "audit_entries",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("subject_type", sa.String(64), nullable=False),
        sa.Column("subject_key", sa.String(128), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_table("audit_entries")
    op.drop_table("replay_records")
    op.drop_table("feedback_records")
    op.drop_table("memory_records")
    op.drop_table("planning_cycles")
    op.drop_table("confidence_calibrations")
    op.drop_table("governance_reviews")
    op.drop_table("rules")
    op.drop_table("strategy_evaluations")
    op.drop_table("strategies")
    op.drop_table("experiments")
    op.drop_table("hypotheses")
    op.drop_table("opportunity_validations")
    op.drop_table("opportunity_rankings")
    op.drop_table("opportunities")
