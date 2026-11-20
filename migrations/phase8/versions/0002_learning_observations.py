from __future__ import annotations
import sqlalchemy as sa
from alembic import op

revision = "0002_learning_observations"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "learning_observations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("observation_id", sa.String(255), nullable=True),
        sa.Column("subject_id", sa.String(255), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("metric_value", sa.Numeric(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_learning_obs_subject_metric", "learning_observations", ["subject_id", "metric_name", "created_at"])

def downgrade() -> None:
    op.drop_index("idx_learning_obs_subject_metric", table_name="learning_observations")
    op.drop_table("learning_observations")
