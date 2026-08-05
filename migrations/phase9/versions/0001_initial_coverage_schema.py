"""initial knowledge coverage schema

Revision ID: 0001
Revises:
Create Date: 2026-01-01 00:00:00

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_coverage",
        sa.Column("coverage_id", sa.String(length=64), primary_key=True),
        sa.Column("knowledge_id", sa.String(length=64), nullable=False),
        sa.Column("coverage_profile_id", sa.String(length=64), nullable=False),
        sa.Column("coverage_profile_name", sa.String(length=128), nullable=False),
        sa.Column("coverage_profile_description", sa.Text(), nullable=True),
        sa.Column("coverage_profile_metadata_json", sa.Text(), nullable=True),
        sa.Column("coverage_score", sa.Float(), nullable=False),
        sa.Column("coverage_confidence", sa.Float(), nullable=False),
        sa.Column("coverage_dimensions_json", sa.Text(), nullable=False),
        sa.Column("detected_gaps_json", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("structural_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("feature_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("fingerprint_hash", sa.String(length=64), nullable=False),
        sa.Column("fingerprint_version", sa.String(length=32), nullable=False),
        sa.Column("engine_version", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("versions_json", sa.Text(), nullable=False),
        sa.Column("explainability_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_knowledge_coverage_knowledge_id", "knowledge_coverage", ["knowledge_id"]
    )
    op.create_index(
        "ix_knowledge_coverage_structural_fingerprint",
        "knowledge_coverage",
        ["structural_fingerprint"],
    )
    op.create_index(
        "ix_knowledge_coverage_feature_fingerprint",
        "knowledge_coverage",
        ["feature_fingerprint"],
    )
    op.create_index(
        "ix_knowledge_coverage_fingerprint_hash",
        "knowledge_coverage",
        ["fingerprint_hash"],
        unique=True,
    )

    op.create_table(
        "coverage_transition",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "coverage_id",
            sa.String(length=64),
            sa.ForeignKey("knowledge_coverage.coverage_id"),
            nullable=False,
        ),
        sa.Column("previous_coverage_id", sa.String(length=64), nullable=True),
        sa.Column("knowledge_id", sa.String(length=64), nullable=False),
        sa.Column("previous_score", sa.Float(), nullable=True),
        sa.Column("new_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_coverage_transition_knowledge_id", "coverage_transition", ["knowledge_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_coverage_transition_knowledge_id", table_name="coverage_transition")
    op.drop_table("coverage_transition")
    op.drop_index("ix_knowledge_coverage_fingerprint_hash", table_name="knowledge_coverage")
    op.drop_index("ix_knowledge_coverage_feature_fingerprint", table_name="knowledge_coverage")
    op.drop_index("ix_knowledge_coverage_structural_fingerprint", table_name="knowledge_coverage")
    op.drop_index("ix_knowledge_coverage_knowledge_id", table_name="knowledge_coverage")
    op.drop_table("knowledge_coverage")
