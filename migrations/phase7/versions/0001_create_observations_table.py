"""
0001 – Create observations table.

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "observations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            primary_key=True,
        ),
        sa.Column("fingerprint", sa.String(64), nullable=False, unique=True),
        sa.Column("execution_id", sa.String(255), nullable=False),
        sa.Column("workflow_id", sa.String(255), nullable=False),
        sa.Column("node_id", sa.String(255), nullable=False),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("context_extra", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("observation_version", sa.String(32), nullable=False),
    )
    op.create_index(
        "ix_observations_fingerprint", "observations", ["fingerprint"], unique=True
    )
    op.create_index(
        "ix_observations_tenant_id", "observations", ["tenant_id"]
    )
    op.create_index(
        "ix_observations_tenant_fingerprint",
        "observations",
        ["tenant_id", "fingerprint"],
    )


def downgrade() -> None:
    op.drop_index("ix_observations_tenant_fingerprint", table_name="observations")
    op.drop_index("ix_observations_tenant_id", table_name="observations")
    op.drop_index("ix_observations_fingerprint", table_name="observations")
    op.drop_table("observations")
