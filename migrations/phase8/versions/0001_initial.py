"""
Initial migration for the Learning Layer.

Revision ID: 0001_initial
Revises: None
Create Date: static (no timestamp, per project determinism rules)

This migration is written in Alembic's op-based style so it can be dropped
into an Alembic environment as-is. It creates all five Learning Layer
tables: knowledge, knowledge_versions, knowledge_transitions,
knowledge_evidence, knowledge_patterns.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# Alembic identifiers
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge",
        sa.Column("knowledge_id", sa.String(length=64), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("fingerprint_hash", sa.String(length=64), nullable=False),
        sa.Column("structural_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("feature_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("knowledge_version", sa.Integer(), nullable=False),
        sa.Column("fingerprint_version", sa.String(length=32), nullable=False),
        sa.Column("engine_version", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("confidence_sample_size", sa.Integer(), nullable=False),
        sa.Column("confidence_consistency", sa.Float(), nullable=False),
        sa.Column("confidence_components", sa.JSON(), nullable=False),
        sa.Column("explainability", sa.JSON(), nullable=False),
        sa.Column(
            "previous_knowledge_id",
            sa.String(length=64),
            sa.ForeignKey("knowledge.knowledge_id"),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "fingerprint_hash", "knowledge_version", name="uq_fingerprint_version"
        ),
    )
    op.create_index(
        "ix_knowledge_fingerprint_hash", "knowledge", ["fingerprint_hash"]
    )

    op.create_table(
        "knowledge_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "knowledge_id",
            sa.String(length=64),
            sa.ForeignKey("knowledge.knowledge_id"),
            nullable=False,
        ),
        sa.Column("knowledge_version", sa.Integer(), nullable=False),
        sa.Column("fingerprint_version", sa.String(length=32), nullable=False),
        sa.Column("engine_version", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("previous_knowledge_id", sa.String(length=64), nullable=True),
        sa.UniqueConstraint(
            "knowledge_id", "knowledge_version", name="uq_knowledge_version"
        ),
    )
    op.create_index(
        "ix_knowledge_versions_knowledge_id", "knowledge_versions", ["knowledge_id"]
    )

    op.create_table(
        "knowledge_transitions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "knowledge_id",
            sa.String(length=64),
            sa.ForeignKey("knowledge.knowledge_id"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.UniqueConstraint(
            "knowledge_id", "sequence", name="uq_transition_sequence"
        ),
    )
    op.create_index(
        "ix_knowledge_transitions_knowledge_id",
        "knowledge_transitions",
        ["knowledge_id"],
    )

    op.create_table(
        "knowledge_evidence",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "knowledge_id",
            sa.String(length=64),
            sa.ForeignKey("knowledge.knowledge_id"),
            nullable=False,
        ),
        sa.Column("observation_id", sa.String(length=64), nullable=False),
        sa.Column("strength", sa.String(length=16), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
            "knowledge_id", "observation_id", name="uq_knowledge_observation"
        ),
    )
    op.create_index(
        "ix_knowledge_evidence_knowledge_id", "knowledge_evidence", ["knowledge_id"]
    )

    op.create_table(
        "knowledge_patterns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "knowledge_id",
            sa.String(length=64),
            sa.ForeignKey("knowledge.knowledge_id"),
            nullable=False,
        ),
        sa.Column("pattern_type", sa.String(length=32), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("signature", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_knowledge_patterns_knowledge_id", "knowledge_patterns", ["knowledge_id"]
    )


def downgrade() -> None:
    op.drop_table("knowledge_patterns")
    op.drop_table("knowledge_evidence")
    op.drop_table("knowledge_transitions")
    op.drop_table("knowledge_versions")
    op.drop_table("knowledge")
