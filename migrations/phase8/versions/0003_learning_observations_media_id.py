from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0003_learning_observations_media_id"
down_revision = "0002_learning_observations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "learning_observations",
        sa.Column("media_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_learning_observations_media_id",
        "learning_observations",
        ["media_id"],
    )
    op.execute(
        sa.text(
            """
            UPDATE learning_observations
            SET media_id = NULLIF((context::jsonb ->> 'media_id'), '')
            WHERE media_id IS NULL
              AND context IS NOT NULL
              AND NULLIF((context::jsonb ->> 'media_id'), '') IS NOT NULL
            """
        )
    )
    op.create_unique_constraint(
        "uq_learning_observations_media_metric",
        "learning_observations",
        ["media_id", "metric_name"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_learning_observations_media_metric",
        "learning_observations",
        type_="unique",
    )
    op.drop_index("ix_learning_observations_media_id", table_name="learning_observations")
    op.drop_column("learning_observations", "media_id")
